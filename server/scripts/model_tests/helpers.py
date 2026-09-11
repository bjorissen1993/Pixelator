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
