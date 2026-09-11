from __future__ import annotations

import json
import re
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[2]
TEST_OUTPUT_ROOT = SERVER_DIR / "test_outputs"


def slugify_model_id(model_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", model_id.strip()).strip("_")
    return slug or "unnamed_model"


def output_dir_for(output_name: str) -> Path:
    return TEST_OUTPUT_ROOT / output_name


def loaded_model_id(pipe) -> str:
    for attr in ("name_or_path",):
        value = getattr(pipe, attr, None)
        if value:
            return str(value)
    config = getattr(pipe, "config", None)
    if config is not None:
        for attr in ("_name_or_path", "name_or_path"):
            value = getattr(config, attr, None)
            if value:
                return str(value)
    return ""


def assert_exact_model(pipe, expected_model_id: str, *, allow_sdxl: bool = False) -> str:
    loaded = loaded_model_id(pipe)
    class_name = type(pipe).__name__
    print(f"requested model id: {expected_model_id}")
    print(f"actual loaded model id: {loaded or '(unknown)'}")
    print(f"pipeline class: {class_name}")
    if not expected_model_id.strip():
        raise RuntimeError("Hard fail: MODEL_ID is empty. Set test_config.MODEL_ID or pass --model.")
    normalized = loaded.replace("\\", "/")
    expected = expected_model_id.replace("\\", "/")
    if expected.lower() not in normalized.lower():
        raise RuntimeError(
            f"Hard fail: loaded model {loaded!r} is not {expected_model_id!r}. Refusing to generate."
        )
    looks_xl = "xl" in class_name.lower() or "sdxl" in class_name.lower()
    path_xl = "sdxl" in normalized.lower() or "stable-diffusion-xl" in normalized.lower()
    if not allow_sdxl and (looks_xl or path_xl):
        raise RuntimeError(
            f"Hard fail: SDXL is not allowed in this isolated South-base test "
            f"(pipeline={class_name}, loaded={loaded!r})."
        )
    return loaded


def cuda_memory(torch_mod) -> str:
    if not torch_mod.cuda.is_available():
        return "n/a"
    used = torch_mod.cuda.max_memory_allocated()
    return f"{used / (1024 ** 3):.2f} GB ({used} bytes)"


def require_cuda(torch_mod) -> None:
    if not torch_mod.cuda.is_available():
        raise RuntimeError("Hard fail: CUDA is unavailable. This isolated test requires a GPU.")


def write_metadata(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_text2image_pipeline(model_id: str, dtype, allow_sdxl: bool):
    from diffusers import DiffusionPipeline, StableDiffusionPipeline

    kwargs = {
        "torch_dtype": dtype,
        "safety_checker": None,
        "requires_safety_checker": False,
    }
    try:
        pipe = StableDiffusionPipeline.from_pretrained(model_id, **kwargs)
    except Exception:
        try:
            from diffusers import AutoPipelineForText2Image

            pipe = AutoPipelineForText2Image.from_pretrained(model_id, torch_dtype=dtype)
        except Exception:
            pipe = DiffusionPipeline.from_pretrained(model_id, torch_dtype=dtype)
    assert_exact_model(pipe, model_id, allow_sdxl=allow_sdxl)
    return pipe


def load_lora_or_fail(pipe, lora_id: str, adapter_name: str = "candidate"):
    if not lora_id:
        raise RuntimeError("Hard fail: LoRA id is empty.")
    if not hasattr(pipe, "load_lora_weights"):
        raise RuntimeError("Hard fail: this pipeline cannot load LoRA weights.")
    print(f"requested LoRA: {lora_id}")
    try:
        pipe.load_lora_weights(lora_id, adapter_name=adapter_name)
    except TypeError:
        pipe.load_lora_weights(lora_id)
    except Exception as exc:
        raise RuntimeError(f"Hard fail: LoRA {lora_id!r} failed to load: {exc}") from exc
    adapters = None
    if hasattr(pipe, "get_list_adapters"):
        try:
            adapters = pipe.get_list_adapters()
        except Exception:
            adapters = None
    if hasattr(pipe, "get_active_adapters"):
        try:
            adapters = adapters or pipe.get_active_adapters()
        except Exception:
            pass
    print(f"actual loaded LoRA: {lora_id}")
    print(f"LoRA adapters: {adapters}")
    if adapters in ([], {}, ()):
        raise RuntimeError(f"Hard fail: LoRA {lora_id!r} loaded without any adapters.")
    return adapter_name


def apply_lora_strength(pipe, adapter_name: str, strength: float) -> dict:
    kwargs = {}
    try:
        if hasattr(pipe, "set_adapters"):
            pipe.set_adapters(adapter_name, adapter_weights=strength)
            print(f"LoRA strength via set_adapters: {strength}")
            return kwargs
    except Exception:
        pass
    kwargs["cross_attention_kwargs"] = {"scale": float(strength)}
    print(f"LoRA strength via cross_attention_kwargs.scale: {strength}")
    return kwargs


def strength_tag(strength: float) -> str:
    return f"strength{int(round(strength * 100)):03d}"
