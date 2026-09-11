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


def _summarize_peft_config(unet) -> dict:
    raw = getattr(unet, "peft_config", None)
    if not raw:
        return {}
    summary = {}
    for name, item in dict(raw).items():
        target = getattr(item, "target_modules", None)
        if isinstance(target, (set, tuple, list)):
            target = sorted(str(x) for x in target)
        summary[str(name)] = {
            "peft_type": str(getattr(item, "peft_type", item)),
            "r": getattr(item, "r", None),
            "lora_alpha": getattr(item, "lora_alpha", None),
            "target_modules": target,
        }
    return summary


def inspect_peft_unet(unet) -> dict:
    from peft import PeftModel

    class_name = type(unet).__name__
    module_name = f"{type(unet).__module__}.{class_name}"
    print("LoRA loader: PEFT UNet adapter (PeftModel.from_pretrained)")
    print(f"UNet class: {module_name}")
    peft_config = _summarize_peft_config(unet)
    print(f"peft_config: {peft_config or '{}'}")
    adapters = list(peft_config.keys()) if peft_config else []
    active = getattr(unet, "active_adapters", None)
    if active:
        adapters = list(dict.fromkeys([*adapters, *(list(active) if not isinstance(active, str) else [active])]))
    print(f"available adapter names: {adapters or '(none)'}")
    total = sum(param.numel() for param in unet.parameters())
    trainable = sum(param.numel() for param in unet.parameters() if param.requires_grad)
    adapter_params = sum(
        param.numel() for name, param in unet.named_parameters() if "lora_" in name.lower() or ".lora" in name.lower()
    )
    print(f"UNet parameters: trainable={trainable:,} total={total:,} adapter-like={adapter_params:,}")
    if not isinstance(unet, PeftModel) and "Peft" not in class_name:
        raise RuntimeError(
            f"Hard fail: UNet remains an ordinary unwrapped model ({module_name}). PEFT adapter did not attach."
        )
    if not peft_config:
        raise RuntimeError("Hard fail: peft_config is empty after PeftModel.from_pretrained.")
    if adapter_params == 0:
        print("WARNING: no lora_* parameter names were found; relying on peft_config presence.")
    return {
        "unet_class": module_name,
        "peft_config": peft_config,
        "adapter_names": adapters,
        "trainable_parameters": trainable,
        "total_parameters": total,
        "adapter_parameters": adapter_params,
    }


def peft_runtime_scale_supported(unet) -> bool:
    # Diffusers set_adapters / cross_attention_kwargs.scale do not control a PEFT-wrapped UNet.
    # Do not walk internal LoraLayer.scaling; that would be fake strength control.
    return False


def load_peft_unet_adapter(pipe, lora_id: str, device: str, dtype):
    if not lora_id:
        raise RuntimeError("Hard fail: LoRA id is empty.")
    print("LoRA loader: PEFT UNet adapter (PeftModel.from_pretrained)")
    print(f"requested LoRA: {lora_id}")
    print("Diffusers load_lora_weights: skipped")
    try:
        from peft import PeftModel
    except Exception as exc:
        raise RuntimeError(f"Hard fail: could not import peft.PeftModel: {exc}") from exc
    try:
        wrapped = PeftModel.from_pretrained(pipe.unet, lora_id)
    except Exception as exc:
        raise RuntimeError(f"Hard fail: PeftModel.from_pretrained({lora_id!r}) failed: {exc}") from exc
    wrapped = wrapped.to(device=device, dtype=dtype)
    wrapped.eval()
    pipe.unet = wrapped
    info = inspect_peft_unet(pipe.unet)
    info["lora_id"] = lora_id
    info["strength_sweep_supported"] = peft_runtime_scale_supported(pipe.unet)
    if not info["strength_sweep_supported"]:
        print(
            "PEFT runtime adapter scaling is not supported cleanly for this UNet wrap. "
            "Strength sweep 0.8 vs 1.0 is temporarily unsupported; generating at native/default adapter strength only."
        )
    return info


def load_lora_or_fail(pipe, lora_id: str, adapter_name: str = "candidate"):
    if not lora_id:
        raise RuntimeError("Hard fail: LoRA id is empty.")
    print("LoRA loader: Diffusers load_lora_weights")
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
