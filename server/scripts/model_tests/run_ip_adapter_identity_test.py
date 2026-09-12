"""Isolated IP-Adapter identity test on PublicPrompts/All-In-One-Pixel-Model.

Not wired into Pixelator. No ControlNet, LoRA, rotation, or 8-dir generation.
Requires a Berwynn South reference image and hard-fails if conditioning is missing.
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import (
    assert_clip_prompt_budget,
    assert_exact_model,
    cuda_memory,
    load_ip_adapter_or_fail,
    load_text2image_pipeline,
    output_dir_for,
    require_cuda,
    sha256_file,
    write_metadata,
)

MODEL_ID = "PublicPrompts/All-In-One-Pixel-Model"
IP_ADAPTER_REPO = "h94/IP-Adapter"
IP_ADAPTER_SUBFOLDER = "models"
IP_ADAPTER_WEIGHT = "ip-adapter-plus_sd15.bin"
OUTPUT_NAME = "publicprompts_ip_adapter_identity"
WIDTH = 512
HEIGHT = 512
STEPS = 30
GUIDANCE = 7.5
SEED = 51721
SCALES = (0.4, 0.6, 0.8, 1.0)

PROMPT = (
    "pixelsprite, elderly male spirit, grey hair, thick grey beard, worn dark village clothing, "
    "spectral ghost tail instead of legs, front facing, full body, centered"
)
NEGATIVE_PROMPT = (
    "legs, boots, armor, weapon, staff, portrait, cropped, multiple characters, "
    "spritesheet, realistic, 3d, text"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Isolated PublicPrompts IP-Adapter identity test.")
    parser.add_argument("--reference", required=True, help="Path to an accepted Berwynn South reference image.")
    return parser.parse_args()


def load_reference_image(raw_path: str):
    from PIL import Image

    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise RuntimeError(f"Hard fail: reference image is missing: {path}")
    try:
        image = Image.open(path)
        image.load()
    except Exception as exc:
        raise RuntimeError(f"Hard fail: could not read reference image {path}: {exc}") from exc
    return path, image.convert("RGB")


def scale_filename(scale: float) -> str:
    return f"ip{int(round(scale * 100)):03d}.png"


def main() -> int:
    args = parse_args()
    out_dir = output_dir_for(OUTPUT_NAME)
    metadata_path = out_dir / "metadata.json"

    print("Isolated IP-Adapter identity test")
    print("Not Pixelator. No ControlNet, LoRA, or rotation.")
    print(f"model_id: {MODEL_ID}")
    print(f"IP-Adapter: {IP_ADAPTER_REPO}/{IP_ADAPTER_SUBFOLDER}/{IP_ADAPTER_WEIGHT}")
    print(f"output directory: {out_dir}")
    print(f"seed: {SEED}")
    print(f"scales: {', '.join(str(scale) for scale in SCALES)}")
    print(f"positive prompt: {PROMPT}")
    print(f"negative prompt: {NEGATIVE_PROMPT}")
    print()

    try:
        import torch
    except Exception:
        print("Failed to import torch", file=sys.stderr)
        traceback.print_exc()
        return 1

    metadata = {"runs": []}
    try:
        require_cuda(torch)
        if not torch.cuda.is_available():
            raise RuntimeError("Hard fail: CUDA is unavailable.")
        device = "cuda"
        dtype = torch.float16
        gpu_name = torch.cuda.get_device_name(0)
        print(f"PyTorch version: {torch.__version__}")
        print(f"CUDA available: True")
        print(f"GPU name: {gpu_name}")
        print(f"device: {device}")
        print(f"dtype: {dtype}")
        print()

        reference_path, reference = load_reference_image(args.reference)
        print(f"reference image: {reference_path}")
        print(f"reference size: {reference.size[0]}x{reference.size[1]}")
        print()

        metadata = {
            "run_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "base_model": MODEL_ID,
            "model_id": MODEL_ID,
            "loaded_model_id": "",
            "ip_adapter_repo": IP_ADAPTER_REPO,
            "ip_adapter_subfolder": IP_ADAPTER_SUBFOLDER,
            "ip_adapter_weight": IP_ADAPTER_WEIGHT,
            "lora": None,
            "controlnet": False,
            "pipeline_class": "",
            "device": device,
            "gpu_name": gpu_name,
            "torch_version": torch.__version__,
            "width": WIDTH,
            "height": HEIGHT,
            "steps": STEPS,
            "guidance": GUIDANCE,
            "seed": SEED,
            "prompt": PROMPT,
            "negative_prompt": NEGATIVE_PROMPT,
            "reference_image_path": str(reference_path),
            "ip_adapter_scales": list(SCALES),
            "runs": [],
        }

        out_dir.mkdir(parents=True, exist_ok=True)
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.empty_cache()

        print("Loading pipeline…")
        load_started = time.perf_counter()
        pipe = load_text2image_pipeline(MODEL_ID, dtype, allow_sdxl=False)
        loaded_id = assert_exact_model(pipe, MODEL_ID, allow_sdxl=False)
        pipe = pipe.to(device)
        ip_info = load_ip_adapter_or_fail(
            pipe,
            IP_ADAPTER_REPO,
            subfolder=IP_ADAPTER_SUBFOLDER,
            weight_name=IP_ADAPTER_WEIGHT,
        )
        pipe = pipe.to(device)
        if getattr(pipe, "image_encoder", None) is None:
            raise RuntimeError("Hard fail: IP-Adapter image encoder disappeared after device move.")
        if not hasattr(pipe, "set_ip_adapter_scale"):
            raise RuntimeError("Hard fail: pipeline cannot set IP-Adapter scale.")
        try:
            embeds = pipe.prepare_ip_adapter_image_embeds(
                ip_adapter_image=reference,
                ip_adapter_image_embeds=None,
                device=device,
                num_images_per_prompt=1,
                do_classifier_free_guidance=True,
            )
        except Exception as exc:
            raise RuntimeError(f"Hard fail: could not encode the reference image for IP-Adapter: {exc}") from exc
        if not embeds:
            raise RuntimeError("Hard fail: IP-Adapter produced empty reference embeddings. Refusing text-only fallback.")

        if hasattr(pipe, "set_progress_bar_config"):
            pipe.set_progress_bar_config(disable=False)
        metadata["loaded_model_id"] = loaded_id
        metadata["pipeline_class"] = type(pipe).__name__
        metadata["ip_adapter"] = ip_info
        metadata["load_seconds"] = round(time.perf_counter() - load_started, 2)
        metadata["clip_tokens"] = assert_clip_prompt_budget(pipe, PROMPT, NEGATIVE_PROMPT)
        write_metadata(metadata_path, metadata)
        print(f"Pipeline loaded in {metadata['load_seconds']:.1f}s")
        print()
        print(f"run_id: {metadata['run_id']}")

        for scale in SCALES:
            filename = scale_filename(scale)
            path = out_dir / filename
            print(f"--- {filename} ---")
            print("REFERENCE CONDITIONING ACTIVE")
            print(f"IP-ADAPTER SCALE: {scale}")
            print(f"exact model id: {loaded_id}")
            print(f"seed: {SEED}")
            print(f"prompt: {PROMPT}")
            print(f"reference image: {reference_path}")
            print(f"output path: {path}")
            print("GENERATING FRESH IMAGE")
            if path.exists():
                print("OVERWRITING EXISTING OUTPUT")
            pipe.set_ip_adapter_scale(scale)
            generator = torch.Generator(device=device).manual_seed(SEED)
            torch.cuda.reset_peak_memory_stats()
            started = time.perf_counter()
            kwargs = {
                "prompt": PROMPT,
                "negative_prompt": NEGATIVE_PROMPT,
                "width": WIDTH,
                "height": HEIGHT,
                "num_inference_steps": STEPS,
                "guidance_scale": GUIDANCE,
                "generator": generator,
                "ip_adapter_image": reference,
            }
            if kwargs.get("ip_adapter_image") is None:
                raise RuntimeError("Hard fail: ip_adapter_image is missing. Refusing text-only fallback.")
            image = pipe(**kwargs).images[0]
            elapsed = time.perf_counter() - started
            image.save(path)
            digest = sha256_file(path)
            memory = cuda_memory(torch)
            metadata["runs"].append(
                {
                    "model_id": loaded_id,
                    "ip_adapter_repo": IP_ADAPTER_REPO,
                    "ip_adapter_weight": IP_ADAPTER_WEIGHT,
                    "ip_adapter_scale": scale,
                    "seed": SEED,
                    "prompt": PROMPT,
                    "negative_prompt": NEGATIVE_PROMPT,
                    "reference_image_path": str(reference_path),
                    "generation_time": round(elapsed, 2),
                    "cuda_memory_usage": memory,
                    "output_path": str(path),
                    "sha256": digest,
                    "device": device,
                    "torch_version": torch.__version__,
                }
            )
            write_metadata(metadata_path, metadata)
            print(f"saved: {path}")
            print(f"sha256: {digest}")
            print(f"elapsed generation time: {elapsed:.2f}s")
            print(f"CUDA memory usage: {memory}")
            print()

        print("Done. Inspect the four IP-Adapter PNGs before any Pixelator integration.")
        print(f"metadata: {metadata_path}")
        return 0
    except Exception:
        print("IP-Adapter identity test failed", file=sys.stderr)
        traceback.print_exc()
        try:
            write_metadata(metadata_path, metadata)
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
