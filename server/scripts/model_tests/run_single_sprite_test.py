"""Isolated single-sprite checkpoint harness.

Not wired into Pixelator. No IP-Adapter, ControlNet, rotation, or 8-dir generation.
Saves raw 512px candidates plus metadata.json under server/test_outputs/<output-name>/.

Examples:
  server\\.venv\\Scripts\\python.exe server\\scripts\\model_tests\\run_single_sprite_test.py --model OWNER/NAME
  server\\.venv\\Scripts\\python.exe server\\scripts\\model_tests\\run_single_sprite_test.py --config varodzak_pixel_art
"""

from __future__ import annotations

import argparse
import importlib
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_config
from helpers import (
    apply_lora_strength,
    assert_clip_prompt_budget,
    assert_exact_model,
    cuda_memory,
    load_lora_or_fail,
    load_peft_unet_adapter,
    load_text2image_pipeline,
    output_dir_for,
    require_cuda,
    slugify_model_id,
    strength_tag,
    write_metadata,
)


def load_named_config(name: str):
    if not name:
        return None
    try:
        return importlib.import_module(f"configs.{name}")
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"Hard fail: unknown test config {name!r}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Isolated single-sprite model test (not Pixelator).")
    parser.add_argument("--config", default="", help="Preset module under configs/, e.g. varodzak_pixel_art")
    parser.add_argument("--model", default="", help="Hugging Face model id or local folder")
    parser.add_argument("--lora", default="", help="Optional LoRA id. Empty means no LoRA.")
    parser.add_argument("--output-name", default="", help="Folder name under server/test_outputs/")
    parser.add_argument("--width", type=int, default=0)
    parser.add_argument("--height", type=int, default=0)
    parser.add_argument("--steps", type=int, default=0)
    parser.add_argument("--guidance", type=float, default=0)
    parser.add_argument("--seeds", default="")
    parser.add_argument("--allow-sdxl", action="store_true", default=False)
    parser.add_argument("--require-cuda", action="store_true", default=False)
    return parser.parse_args()


def parse_seeds(raw: str, fallback: tuple[int, ...]) -> tuple[int, ...]:
    source = raw.strip() if raw.strip() else ",".join(str(seed) for seed in fallback)
    seeds = tuple(int(part.strip()) for part in source.split(",") if part.strip())
    if not seeds:
        raise RuntimeError("No seeds configured.")
    return seeds


def warn_if_rejected(model_id: str, lora_id: str = "") -> None:
    keys = [key for key in (model_id, lora_id) if key]
    seen: set[str] = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        info = test_config.REJECTED_SOUTH_BASE_MODELS.get(key)
        if not info:
            continue
        print(f"WARNING: {key} is rejected as Pixelator's canonical South-base generator.")
        for reason in info.get("reasons", []):
            print(f"  - {reason}")
        print("This run is comparison-only. Do not integrate it into production.")
        print()


def cfg_get(mod, name, default=None):
    if mod is None:
        return default
    return getattr(mod, name, default)


def main() -> int:
    args = parse_args()
    preset = load_named_config(args.config) if args.config else None

    model_id = (args.model or cfg_get(preset, "MODEL_ID") or test_config.MODEL_ID or "").strip()
    lora_id = (args.lora or cfg_get(preset, "LORA") or "").strip()
    lora_loader = (cfg_get(preset, "LORA_LOADER") or "diffusers").strip().lower()
    adapter_name = cfg_get(preset, "LORA_ADAPTER_NAME", "candidate")
    lora_strengths = tuple(cfg_get(preset, "LORA_STRENGTHS") or ())
    seeds = parse_seeds(args.seeds, cfg_get(preset, "SEEDS") or test_config.SEEDS)
    width = args.width or cfg_get(preset, "WIDTH") or test_config.WIDTH
    height = args.height or cfg_get(preset, "HEIGHT") or test_config.HEIGHT
    steps = args.steps or cfg_get(preset, "STEPS") or test_config.STEPS
    guidance = args.guidance or cfg_get(preset, "GUIDANCE") or test_config.GUIDANCE
    allow_sdxl = args.allow_sdxl or bool(cfg_get(preset, "ALLOW_SDXL", test_config.ALLOW_SDXL))
    require_gpu = args.require_cuda or bool(cfg_get(preset, "REQUIRE_CUDA", False))
    negative = cfg_get(preset, "NEGATIVE_PROMPT") or test_config.NEGATIVE_PROMPT
    prompt = cfg_get(preset, "PROMPT")
    prompts = {"A": prompt} if prompt else dict(cfg_get(preset, "PROMPTS") or test_config.PROMPTS)
    output_name = (args.output_name or cfg_get(preset, "OUTPUT_NAME") or "").strip() or slugify_model_id(model_id)
    out_dir = output_dir_for(output_name)
    metadata_path = out_dir / "metadata.json"

    print("Isolated single-sprite model test")
    print("Not Pixelator. No IP-Adapter, ControlNet, or rotation.")
    if args.config:
        print(f"config: {args.config}")
    print(f"output dir: {out_dir}")
    print()

    if not model_id:
        print("Hard fail: set MODEL_ID, pass --model, or use --config", file=sys.stderr)
        return 1
    print(f"adapters: LoRA={'on ' + lora_id if lora_id else 'off'} IP-Adapter=off ControlNet=off")
    if lora_id:
        if lora_loader == "peft_unet":
            print("LoRA loader: PEFT UNet adapter (PeftModel.from_pretrained)")
        else:
            print("LoRA loader: Diffusers load_lora_weights")
    warn_if_rejected(model_id, lora_id)

    try:
        import torch
    except Exception:
        print("Failed to import torch", file=sys.stderr)
        traceback.print_exc()
        return 1

    metadata = {"runs": []}
    try:
        if require_gpu:
            require_cuda(torch)
        cuda_ok = torch.cuda.is_available()
        if require_gpu and not cuda_ok:
            raise RuntimeError("Hard fail: CUDA is unavailable.")
        device = "cuda" if cuda_ok else "cpu"
        dtype = torch.float16 if cuda_ok else torch.float32
        gpu_name = torch.cuda.get_device_name(0) if cuda_ok else "none"
        print(f"PyTorch version: {torch.__version__}")
        print(f"CUDA available: {cuda_ok}")
        print(f"GPU name: {gpu_name}")
        print(f"device: {device}")
        print(f"dtype: {dtype}")
        if not cuda_ok:
            print("WARNING: CUDA is not available. Falling back to CPU float32.")
        print()

        metadata = {
            "base_model": model_id,
            "model_id": model_id,
            "loaded_model_id": "",
            "lora": lora_id or None,
            "lora_loader": lora_loader if lora_id else None,
            "lora_strengths": list(lora_strengths) if lora_strengths else None,
            "pipeline_class": "",
            "device": device,
            "gpu_name": gpu_name,
            "torch_version": torch.__version__,
            "width": width,
            "height": height,
            "steps": steps,
            "guidance": guidance,
            "negative_prompt": negative,
            "allow_sdxl": bool(allow_sdxl),
            "ip_adapter": False,
            "controlnet": False,
            "runs": [],
        }

        out_dir.mkdir(parents=True, exist_ok=True)
        if cuda_ok:
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.empty_cache()

        print("Loading pipeline…")
        load_started = time.perf_counter()
        peft_info = None
        pipe = load_text2image_pipeline(model_id, dtype, allow_sdxl=bool(allow_sdxl))
        loaded_id = assert_exact_model(pipe, model_id, allow_sdxl=bool(allow_sdxl))
        pipe = pipe.to(device)
        if lora_id and lora_loader == "peft_unet":
            if not cuda_ok:
                raise RuntimeError("Hard fail: CUDA is unavailable.")
            peft_info = load_peft_unet_adapter(pipe, lora_id, device=device, dtype=dtype)
            if not torch.cuda.is_available():
                raise RuntimeError("Hard fail: CUDA became unavailable after PEFT UNet wrap.")
            metadata["peft"] = peft_info
            metadata["strength_sweep_supported"] = bool(peft_info.get("strength_sweep_supported"))
        elif lora_id:
            print("LoRA loader: Diffusers load_lora_weights")
            load_lora_or_fail(pipe, lora_id, adapter_name=adapter_name)
            metadata["strength_sweep_supported"] = True
        elif cfg_get(preset, "LORA"):
            raise RuntimeError("Hard fail: config requires a LoRA but none was loaded.")
        if hasattr(pipe, "set_progress_bar_config"):
            pipe.set_progress_bar_config(disable=False)
        metadata["loaded_model_id"] = loaded_id
        metadata["pipeline_class"] = type(pipe).__name__
        metadata["load_seconds"] = round(time.perf_counter() - load_started, 2)
        unique_prompts = [prompt] if prompt else list(prompts.values())
        token_budget = assert_clip_prompt_budget(pipe, unique_prompts[0], negative)
        for extra_prompt in unique_prompts[1:]:
            assert_clip_prompt_budget(pipe, extra_prompt, negative)
        metadata["clip_tokens"] = token_budget
        write_metadata(metadata_path, metadata)
        print(f"Pipeline loaded in {metadata['load_seconds']:.1f}s")
        print()

        jobs = []
        peft_native_only = bool(lora_id) and lora_loader == "peft_unet" and not (peft_info or {}).get("strength_sweep_supported")
        if peft_native_only:
            print("Generating 4 native-strength images. Requested 0.8/1.0 sweep is not applied.")
            single_prompt = prompt or next(iter(prompts.values()))
            for seed in seeds:
                jobs.append(("strength_native", single_prompt, seed, None))
        elif lora_id and lora_strengths:
            single_prompt = prompt or next(iter(prompts.values()))
            for strength in lora_strengths:
                for seed in seeds:
                    jobs.append((strength_tag(strength), single_prompt, seed, float(strength)))
        else:
            for variant, text in prompts.items():
                for seed in seeds:
                    jobs.append((f"variant{variant}", text, seed, None))
        if len(jobs) < 8:
            print(f"NOTE: this run will write {len(jobs)} images (8 expected when a strength sweep is supported).")

        for label, text, seed, strength in jobs:
            filename = f"{label}_seed{seed}.png" if (strength is not None or label.startswith("strength")) else f"{label}_{seed}.png"
            path = out_dir / filename
            extra = {}
            print(f"--- {filename} ---")
            print(f"generation seed: {seed}")
            if strength is not None and lora_loader != "peft_unet":
                print(f"LoRA strength: {strength}")
                extra = apply_lora_strength(pipe, adapter_name, strength)
            elif peft_native_only:
                print("LoRA strength: native/default (PEFT strength sweep unsupported)")
            generator = torch.Generator(device=device).manual_seed(seed)
            if cuda_ok:
                torch.cuda.reset_peak_memory_stats()
            started = time.perf_counter()
            image = pipe(
                prompt=text,
                negative_prompt=negative,
                width=width,
                height=height,
                num_inference_steps=steps,
                guidance_scale=guidance,
                generator=generator,
                **extra,
            ).images[0]
            elapsed = time.perf_counter() - started
            image.save(path)
            memory = cuda_memory(torch)
            metadata["runs"].append(
                {
                    "base_model": loaded_id,
                    "lora": lora_id or None,
                    "lora_loader": lora_loader if lora_id else None,
                    "lora_strength": "native/default" if peft_native_only else strength,
                    "prompt": text,
                    "negative_prompt": negative,
                    "seed": seed,
                    "generation_time": round(elapsed, 2),
                    "cuda_memory_usage": memory,
                    "output_path": str(path),
                    "device": device,
                    "torch_version": torch.__version__,
                }
            )
            write_metadata(metadata_path, metadata)
            print(f"saved: {path}")
            print(f"elapsed generation time: {elapsed:.2f}s")
            print(f"CUDA memory usage: {memory}")
            print()

        print("Done. Inspect the raw PNGs before any Pixelator integration.")
        print(f"metadata: {metadata_path}")
        return 0
    except Exception:
        print("Single-sprite model test failed", file=sys.stderr)
        traceback.print_exc()
        try:
            write_metadata(metadata_path, metadata)
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
