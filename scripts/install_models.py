from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Download local Meet Assistant models to D drive")
    parser.add_argument("--runtime", required=True, type=Path)
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    models = runtime / "models"
    cache = runtime / "cache" / "huggingface"
    models.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.update(
        {
            "HF_HOME": str(cache),
            "HUGGINGFACE_HUB_CACHE": str(cache / "hub"),
            "XDG_CACHE_HOME": str(runtime / "cache"),
            "TMP": str(runtime / "tmp"),
            "TEMP": str(runtime / "tmp"),
            "HF_HUB_DISABLE_XET": "1",
        }
    )

    from huggingface_hub import snapshot_download

    print("Downloading Faster Whisper Medium (about 1.5 GB)...", flush=True)
    snapshot_download(
        repo_id="Systran/faster-whisper-medium",
        local_dir=models / "faster-whisper-medium",
        max_workers=1,
    )
    print("Whisper model ready.", flush=True)


if __name__ == "__main__":
    main()
