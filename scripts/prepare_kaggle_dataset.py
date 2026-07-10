"""Package the generated datasets for upload as a Kaggle Dataset.

Copies sft.jsonl / dpo.jsonl into data/kaggle_upload/ with a dataset-metadata.json,
then prints the `kaggle` CLI commands to create or version the dataset.

Usage:
    python scripts/prepare_kaggle_dataset.py --user YOUR_KAGGLE_USERNAME
"""

from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
import json
import shutil

from sdx.config import DATA_DIR, GENERATED_DIR

UPLOAD_DIR = DATA_DIR / "kaggle_upload"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True, help="your Kaggle username (dataset owner)")
    ap.add_argument("--slug", default="sdx-dataset", help="dataset slug")
    ap.add_argument("--title", default="System Design Expert SFT+DPO dataset")
    args = ap.parse_args()

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in ("sft.jsonl", "dpo.jsonl"):
        src = GENERATED_DIR / name
        if src.exists():
            shutil.copy2(src, UPLOAD_DIR / name)
            copied.append(name)
        else:
            print(f"WARN {src} not found (skipping)")

    meta = {
        "title": args.title,
        "id": f"{args.user}/{args.slug}",
        "licenses": [{"name": "CC0-1.0"}],
    }
    (UPLOAD_DIR / "dataset-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"Prepared {copied} in {UPLOAD_DIR}")
    print("\nCreate (first time):")
    print(f"  kaggle datasets create -p {UPLOAD_DIR} --dir-mode zip")
    print("Version (subsequent updates):")
    print(f'  kaggle datasets version -p {UPLOAD_DIR} -m "update" --dir-mode zip')
    print("\nThen in the notebooks set:")
    print(f"  SFT_PATH = '/kaggle/input/{args.slug}/sft.jsonl'")
    print(f"  DPO_PATH = '/kaggle/input/{args.slug}/dpo.jsonl'")


if __name__ == "__main__":
    main()
