"""Isolated single-sprite checkpoint harness.

Not wired into Pixelator. No LoRA, IP-Adapter, ControlNet, rotation, or 8-dir generation.
Saves raw 512px candidates plus metadata.json under server/test_outputs/<output-name>/.

Examples:
  server\\.venv\\Scripts\\python.exe server\\scripts\\model_tests\\run_single_sprite_test.py --model OWNER/NAME
  server\\.venv\\Scripts\\python.exe server\\scripts\\model_tests\\run_single_sprite_test.py --model OWNER/NAME --output-name my_candidate
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_config
from helpers import (
    assert_exact_model,
    cuda_memory,
    load_text2image_pipeline,
    output_dir_for,
    slugify_model_id,
    write_metadata,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Isolated single-sprite model test (not Pixelator).")
    parser.add_argument("--model", default=test_config.MODEL_ID, help="Hugging Face model id or local folder")
    parser.add_argument("--output-name", default=test_config.OUTPUT_NAME, help="Folder name under server/test_outputs/")
    parser.add_argument("--width", type=int, default=test_config.WIDTH)
    parser.add_argument("--height", type=int, default=test_config.HEIGHT)
    parser.add_argument("--steps", type=int, default=test_config.STEPS)
    parser.add_argument("--guidance", type=float, default=test_config.GUIDANCE)
    parser.add_argument("--seeds", default=",".join(str(seed) for seed in test_config.SEEDS))
    parser.add_argument("--allow-sdxl", action="store_true", default=test_config.ALLOW_SDXL)
    return parser.parse_args()


def parse_seeds(raw: str) -> tuple[int, ...]:
    seeds = tuple(int(part.strip()) for part in raw.split(",") if part.strip())
    if not seeds:
        raise RuntimeError("No seeds configured.")
    return seeds


def warn_if_rejected(model_id: str) -> None:
    info = test_config.REJECTED_SOUTH_BASE_MODELS.get(model_id)
    if not info:
        return
    print(f"WARNING: {model_id} is rejected as Pixelator's canonical South-base generator.")
    for reason in info.get("reasons", []):
        print(f"  - {reason}")
    print("This run is comparison-only. Do not integrate it into production.")
    print()


def main() -> int:
    args = parse_args()
    model_id = (args.model or "").strip()
    seeds = parse_seeds(args.seeds)
    prompts = test_config.PROMPTS
    if len(prompts) * len(seeds) < 8:
        print("WARNING: configured variants x seeds is under 8 images.")
    output_name = (args.output_name or "").strip() or slugify_model_id(model_id)
    out_dir = output_dir_for(output_name)
    metadata_path = out_dir / "metadata.json"

    print("Isolated single-sprite model test")
    print("Not Pixelator. No LoRA, IP-Adapter, ControlNet, or rotation.")
    print(f"output dir: {out_dir}")
    print()

    if not model_id:
        print("Hard fail: set MODEL_ID in test_config.py or pass --model OWNER/NAME", file=sys.stderr)
        return 1
    print("adapters: LoRA=off IP-Adapter=off ControlNet=off")
    warn_if_rejected(model_id)

    try:
        import torch
    except Exception:
        print("Failed to import torch", file=sys.stderr)
        traceback.print_exc()
        return 1

    cuda_ok = torch.cuda.is_available()
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
        "model_id": model_id,
        "loaded_model_id": "",
        "pipeline_class": "",
        "device": device,
        "gpu_name": gpu_name,
        "torch_version": torch.__version__,
        "width": args.width,
        "height": args.height,
        "steps": args.steps,
        "guidance": args.guidance,
        "negative_prompt": test_config.NEGATIVE_PROMPT,
        "allow_sdxl": bool(args.allow_sdxl),
        "lora": False,
        "ip_adapter": False,
        "controlnet": False,
        "runs": [],
    }

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        if cuda_ok:
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.empty_cache()

        print("Loading pipeline…")
        load_started = time.perf_counter()
        pipe = load_text2image_pipeline(model_id, dtype, allow_sdxl=bool(args.allow_sdxl))
        loaded_id = assert_exact_model(pipe, model_id, allow_sdxl=bool(args.allow_sdxl))
        pipe = pipe.to(device)
        if hasattr(pipe, "set_progress_bar_config"):
            pipe.set_progress_bar_config(disable=False)
        metadata["loaded_model_id"] = loaded_id
        metadata["pipeline_class"] = type(pipe).__name__
        metadata["load_seconds"] = round(time.perf_counter() - load_started, 2)
        write_metadata(metadata_path, metadata)
        print(f"Pipeline loaded in {metadata['load_seconds']:.1f}s")
        print()

        for variant, prompt in prompts.items():
            for seed in seeds:
                filename = f"variant{variant}_{seed}.png"
                path = out_dir / filename
                print(f"--- variant {variant} seed {seed} ---")
                print(f"generation seed: {seed}")
                generator = torch.Generator(device=device).manual_seed(seed)
                if cuda_ok:
                    torch.cuda.reset_peak_memory_stats()
                started = time.perf_counter()
                image = pipe(
                    prompt=prompt,
                    negative_prompt=test_config.NEGATIVE_PROMPT,
                    width=args.width,
                    height=args.height,
                    num_inference_steps=args.steps,
                    guidance_scale=args.guidance,
                    generator=generator,
                ).images[0]
                elapsed = time.perf_counter() - started
                image.save(path)
                memory = cuda_memory(torch)
                metadata["runs"].append(
                    {
                        "model_id": loaded_id,
                        "prompt": prompt,
                        "negative_prompt": test_config.NEGATIVE_PROMPT,
                        "seed": seed,
                        "variant": variant,
                        "output_file_path": str(path),
                        "generation_time": round(elapsed, 2),
                        "cuda_memory_usage": memory,
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
