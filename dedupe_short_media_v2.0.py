"""
Cross-Folder Media Dedupe Toolkit v2.0

DESCRIPTION:
- Compare Folder A + Folder B recursively
- Detect duplicates via perceptual hashing (images/videos/gifs)
- Output results with optional "proof mode"

P.S.
- For filename-based dedupe, use a different script.
- For content-based dedupe, use this one.
- This script is ideal for short-form videos & static images. For movie-length files recreate using full perceptual video hashing. 

Status: 
- Confirmed working for images and .mp4 videos.
- Untested for GIFs.

MODES:
1. PROOF MODE (default)
   - Duplicates are copied/moved into output folder (C)
     * Each original folder keeps one unique image, and the duplicate folder stores both matching copies.
   - Keeps audit trail of what was removed/merged

2. NO-PROOF MODE
   - No output folder usage
   - Only cleans/moves files silently

BEHAVIOR:
- Folder A = master (never modified except copying duplicates)
- Folder B = secondary (duplicates are moved out)
- Output folder C = evidence store (optional)

INSTALL:
pip install pillow imagehash opencv-python

USAGE:

CLI MODE:
python dedupe_toolkit.py --a "pathA" --b "pathB" --out "pathC" --no-proof

INTERACTIVE MODE:
python dedupe_toolkit.py
(then script will ask for missing args)

FLAGS:
--a           Folder A
--b           Folder B
--out         Output folder C
--no-proof    Disable proof mode (no output folder usage)
"""

import argparse
from pathlib import Path
import imagehash
from PIL import Image
import cv2
import shutil
import sys

# =========================
# CONFIG
# =========================
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".avi", ".mov"}


# =========================
# HASHING
# =========================
def hash_image(path: Path):
    try:
        with Image.open(path) as img:
            return str(imagehash.phash(img))
    except:
        return None


def hash_video(path: Path):
    try:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return None

        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if frames <= 0:
            cap.release()
            return None

        cap.set(cv2.CAP_PROP_POS_FRAMES, frames // 2)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            return None

        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        return str(imagehash.phash(img))

    except:
        return None


def get_hash(path: Path):
    ext = path.suffix.lower()

    if ext in IMAGE_EXTS:
        return hash_image(path)

    if ext in VIDEO_EXTS:
        return hash_video(path)

    return None


# =========================
# FILE COLLECTION
# =========================
def collect(folder: Path):
    return [f for f in folder.rglob("*") if f.is_file()]


# =========================
# SAFE PATH GENERATOR
# =========================
def safe_path(folder: Path, name: str):
    target = folder / name
    if not target.exists():
        return target

    base = target.stem
    ext = target.suffix

    i = 2
    while True:
        new = folder / f"{base}_{i}{ext}"
        if not new.exists():
            return new
        i += 1


# =========================
# ARG PARSING + INTERACTIVE FALLBACK
# =========================
def get_args():
    parser = argparse.ArgumentParser(description="Media Dedupe Toolkit v1.4")

    parser.add_argument("--a", type=str, help="Folder A (master)")
    parser.add_argument("--b", type=str, help="Folder B (secondary)")
    parser.add_argument("--out", type=str, help="Output folder (proof storage)")
    parser.add_argument("--no-proof", action="store_true", help="Disable proof output")

    args = parser.parse_args()

    # Interactive fallback
    if not args.a:
        args.a = input("Enter Folder A (master): ").strip('" ')
    if not args.b:
        args.b = input("Enter Folder B (secondary): ").strip('" ')

    if not args.no_proof and not args.out:
        args.out = input("Enter Output Folder C (proof store): ").strip('" ')

    return args


# =========================
# MAIN LOGIC
# =========================
def main():
    args = get_args()

    folder_a = Path(args.a)
    folder_b = Path(args.b)
    folder_c = Path(args.out) if args.out else None

    proof_mode = not args.no_proof

    if not folder_a.exists() or not folder_b.exists():
        print("❌ Invalid input folders.")
        sys.exit(1)

    if proof_mode and folder_c:
        folder_c.mkdir(parents=True, exist_ok=True)
        print(f"📁 Proof mode ENABLED → {folder_c}")
    else:
        print("⚡ Proof mode DISABLED")

    files_a = collect(folder_a)
    files_b = collect(folder_b)

    seen = {}
    group = 1

    print("\n--- Processing Folder A (MASTER) ---\n")

    for f in files_a:
        h = get_hash(f)
        if not h:
            continue

        if h not in seen:
            seen[h] = ("A", f)
        else:
            # duplicate in A
            if proof_mode and folder_c:
                target1 = safe_path(folder_c, f"{group}{f.suffix.lower()}")
                target2 = safe_path(folder_c, f"{group} (dupe){f.suffix.lower()}")

                print(f"📋 A DUP → {f.name}")

                shutil.copy2(f, target1)
                shutil.copy2(seen[h][1], target2)

                group += 1


    print("\n--- Processing Folder B (SECONDARY) ---\n")

    for f in files_b:
        h = get_hash(f)
        if not h:
            continue

        if h not in seen:
            seen[h] = ("B", f)
        else:
            origin, original = seen[h]

            if proof_mode and folder_c:
                target = safe_path(folder_c, f"{group}{f.suffix.lower()}")
                print(f"📦 B DUP → {f.name} → {target.name}")
                shutil.move(str(f), target)

                if origin == "A":
                    proof = safe_path(folder_c, f"{group} (dupe){original.suffix.lower()}")
                    shutil.copy2(original, proof)

                group += 1
            else:
                print(f"🗑 B DUP (silent) → {f.name}")
                shutil.move(str(f), folder_b / f.name)


    print("\n========================")
    print(f"Groups: {group - 1}")
    print("========================\n")


if __name__ == "__main__":
    main()