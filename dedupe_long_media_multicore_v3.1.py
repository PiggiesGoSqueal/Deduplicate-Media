"""
Cross-Folder Media Toolkit v3.1 (multicore)

Purpose
-------
Compares two folder trees:

  Folder A = master (source of truth)
  Folder B = secondary (cleaned)

Uses content-based matching (not filenames).

Behavior
--------
- If a duplicate is found, the file in Folder B is removed (moved or deleted).
- Folder A is never modified (except optional proof copies).
- Optional output folder stores copies of duplicates for auditing.

Result
------
After running:
- Folder A contains original media.
- Folder B contains only files not found in Folder A.
- No duplicates remain across both folders.

Modes
-----
Proof mode (default):
- Duplicates are copied/moved to an output folder for verification.

No-proof mode (--no-proof):
- No output folder.
- Duplicates are removed from Folder B without keeping copies.

Detection
---------
Images:
- Perceptual hash (phash), tolerant to resizing/compression.

Videos:
- Multi-frame fingerprint (0%, 25%, 50%, 75%, last frame).
- Each frame hashed with phash.
- Compared using overlap ratio (~60%).

Performance
-----------
- Multicore hashing via ProcessPoolExecutor.
- Default workers: CPU cores - 3.
- Hashing is parallel; matching is single-threaded.

Requirements
------------
pip install pillow imagehash opencv-python

Usage
-----
CLI:
  python dedupe_long_media_v3.1_multicore.py \
      --a "PATH_TO_FOLDER_A" \
      --b "PATH_TO_FOLDER_B" \
      --out "PATH_TO_OUTPUT_FOLDER"

Interactive:
  python dedupe_long_media_v3.1_multicore.py

Arguments
---------
--a        Folder A (master, never modified)
--b        Folder B (secondary, cleaned)
--out      Output folder (proof storage)
--no-proof Disable proof mode
"""

import argparse
import os
from pathlib import Path
import imagehash
from PIL import Image
import cv2
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed


# =========================
# FILE TYPE CONFIG
# =========================
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".avi", ".mov"}


# =========================
# IMAGE HASHING
# =========================
def hash_image(path_str):
    try:
        path = Path(path_str)
        with Image.open(path) as img:
            return str(imagehash.phash(img))
    except:
        return None


# =========================
# VIDEO HASHING (MULTI-FRAME)
# =========================
def hash_video(path_str):
    """
    Creates a fingerprint from multiple sampled frames.
    Returns a frozenset so it can be safely stored as a dict key.
    """

    try:
        path = Path(path_str)
        cap = cv2.VideoCapture(str(path))

        if not cap.isOpened():
            return None

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count <= 0:
            cap.release()
            return None

        sample_points = [
            0,
            frame_count // 4,
            frame_count // 2,
            (frame_count * 3) // 4,
            frame_count - 1
        ]

        hashes = set()

        for frame_no in sample_points:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = cap.read()

            if not ret:
                continue

            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            hashes.add(str(imagehash.phash(img)))

        cap.release()

        return frozenset(hashes) if hashes else None

    except:
        return None


# =========================
# MULTICORE WORKER
# =========================
def worker_hash(file_path):
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext in IMAGE_EXTS:
        return (file_path, hash_image(file_path))

    if ext in VIDEO_EXTS:
        return (file_path, hash_video(file_path))

    return (file_path, None)


# =========================
# RECURSIVE FILE COLLECTION
# =========================
def collect(folder: Path):
    return [str(f) for f in folder.rglob("*") if f.is_file()]


# =========================
# SIMILARITY LOGIC
# =========================
def video_match(h1, h2):
    if not isinstance(h1, frozenset) or not isinstance(h2, frozenset):
        return False

    overlap = len(h1.intersection(h2))
    total = max(len(h1), len(h2))

    return total > 0 and (overlap / total) >= 0.6


def image_match(h1, h2):
    try:
        return imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2) <= 5
    except:
        return False


def is_duplicate(h1, h2):
    if isinstance(h1, frozenset) or isinstance(h2, frozenset):
        return video_match(h1, h2)
    return image_match(h1, h2)


# =========================
# SAFE OUTPUT PATH
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
# ARGUMENT PARSER
# =========================
def get_args():
    parser = argparse.ArgumentParser(
        description="Multicore Long Media Dedupe Toolkit v3.1"
    )

    parser.add_argument("--a", help="Folder A (MASTER - NOT modified)")
    parser.add_argument("--b", help="Folder B (SECONDARY - WILL be cleaned)")
    parser.add_argument("--out", help="Output folder (proof storage)")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--no-proof", action="store_true")

    args = parser.parse_args()

    if not args.a:
        args.a = input("Folder A (MASTER): ").strip('" ')
    if not args.b:
        args.b = input("Folder B (SECONDARY): ").strip('" ')

    if not args.no_proof and not args.out:
        args.out = input("Output Folder (proof): ").strip('" ')

    return args


# =========================
# MAIN EXECUTION
# =========================
def main():
    args = get_args()

    folder_a = Path(args.a)
    folder_b = Path(args.b)
    folder_c = Path(args.out) if args.out else None

    proof = not args.no_proof

    # Validate inputs
    if not folder_a.exists() or not folder_b.exists():
        print("❌ Invalid folder paths.")
        sys.exit(1)

    # Proof mode setup
    if proof and folder_c:
        folder_c.mkdir(parents=True, exist_ok=True)
        print(f"\n📁 Proof mode ENABLED → {folder_c}")
    else:
        print("\n⚡ Proof mode DISABLED (no duplicate archive)\n")

    # =========================
    # CPU WORKER CONFIG
    # =========================
    cpu = os.cpu_count() or 4
    workers = args.workers or max(1, cpu - 3)

    print(f"⚡ Using {workers} CPU workers (CPU cores - 3)\n")

    files_a = collect(folder_a)
    files_b = collect(folder_b)
    all_files = files_a + files_b

    # =========================
    # MULTICORE HASHING PHASE
    # =========================
    print("⚡ Hashing files (multicore)...\n")

    results = {}

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker_hash, f) for f in all_files]

        for future in as_completed(futures):
            file_path, h = future.result()
            results[file_path] = h

    # =========================
    # DEDUPLICATION PHASE
    # =========================
    print("\n--- DEDUPLICATION START ---\n")

    seen = {}
    group = 1

    # Folder A scan
    for f in files_a:
        h = results.get(f)
        if not h:
            continue

        if h not in seen:
            seen[h] = ("A", f)
        else:
            if proof and folder_c:
                print(f"📋 DUP FOUND IN A → {Path(f).name}")

                shutil.copy2(f, safe_path(folder_c, f"{group}{Path(f).suffix}"))
                shutil.copy2(seen[h][1], safe_path(folder_c, f"{group} (dupe){Path(f).suffix}"))

                group += 1

    # Folder B scan (THIS is where removal happens)
    for f in files_b:
        h = results.get(f)
        if not h:
            continue

        matched = False

        for existing_h, (origin, original) in seen.items():
            if is_duplicate(h, existing_h):
                matched = True

                # 🚨 CRITICAL BEHAVIOR:
                # THIS FILE IS REMOVED FROM FOLDER B
                print(f"🗑 REMOVING DUPLICATE FROM FOLDER B → {Path(f).name}")

                if proof and folder_c:
                    shutil.move(f, safe_path(folder_c, f"{group}{Path(f).suffix}"))

                    if origin == "A":
                        shutil.copy2(
                            original,
                            safe_path(folder_c, f"{group} (dupe){Path(original).suffix}")
                        )
                else:
                    # No-proof mode = still removed from B
                    shutil.move(f, folder_b / Path(f).name)

                group += 1
                break

        if not matched:
            seen[h] = ("B", f)

    print("\n========================")
    print("✔ Deduplication complete")
    print(f"Groups found: {group - 1}")
    print("========================\n")


if __name__ == "__main__":
    main()

import argparse
import os
from pathlib import Path
import imagehash
from PIL import Image
import cv2
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

# =========================
# CONFIG
# =========================
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".avi", ".mov"}


# =========================
# IMAGE HASH
# =========================
def hash_image(path_str):
    try:
        path = Path(path_str)
        with Image.open(path) as img:
            return str(imagehash.phash(img))
    except:
        return None


# =========================
# VIDEO HASH (FRAME SET)
# =========================
def hash_video(path_str):
    try:
        path = Path(path_str)
        cap = cv2.VideoCapture(str(path))

        if not cap.isOpened():
            return None

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count <= 0:
            cap.release()
            return None

        sample_points = [
            0,
            frame_count // 4,
            frame_count // 2,
            (frame_count * 3) // 4,
            frame_count - 1
        ]

        hashes = set()

        for frame_no in sample_points:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ret, frame = cap.read()

            if not ret:
                continue

            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            hashes.add(str(imagehash.phash(img)))

        cap.release()

        return frozenset(hashes) if hashes else None

    except:
        return None


# =========================
# MULTICORE WORKER
# =========================
def worker_hash(file_path):
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext in IMAGE_EXTS:
        return (file_path, hash_image(file_path))

    if ext in VIDEO_EXTS:
        return (file_path, hash_video(file_path))

    return (file_path, None)


# =========================
# FILE COLLECTION (RECURSIVE)
# =========================
def collect(folder: Path):
    return [str(f) for f in folder.rglob("*") if f.is_file()]


# =========================
# VIDEO MATCH
# =========================
def video_match(h1, h2):
    if not isinstance(h1, frozenset) or not isinstance(h2, frozenset):
        return False

    overlap = len(h1.intersection(h2))
    total = max(len(h1), len(h2))

    return total > 0 and (overlap / total) >= 0.6


# =========================
# IMAGE MATCH
# =========================
def image_match(h1, h2):
    try:
        return imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2) <= 5
    except:
        return False


# =========================
# MATCH ROUTER
# =========================
def is_duplicate(h1, h2):
    if isinstance(h1, frozenset) or isinstance(h2, frozenset):
        return video_match(h1, h2)
    return image_match(h1, h2)


# =========================
# SAFE OUTPUT PATH
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
# ARG PARSER
# =========================
def get_args():
    parser = argparse.ArgumentParser(
        description="Dedupe LONG Media v3.1 Multicore"
    )

    parser.add_argument("--a", help="Folder A (master)")
    parser.add_argument("--b", help="Folder B (secondary)")
    parser.add_argument("--out", help="Output folder (proof mode)")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--no-proof", action="store_true")

    args = parser.parse_args()

    if not args.a:
        args.a = input("Folder A: ").strip('" ')
    if not args.b:
        args.b = input("Folder B: ").strip('" ')

    if not args.no_proof and not args.out:
        args.out = input("Output Folder: ").strip('" ')

    return args


# =========================
# MAIN
# =========================
def main():
    args = get_args()

    folder_a = Path(args.a)
    folder_b = Path(args.b)
    folder_c = Path(args.out) if args.out else None

    proof = not args.no_proof

    if not folder_a.exists() or not folder_b.exists():
        print("❌ Invalid folders.")
        sys.exit(1)

    if proof and folder_c:
        folder_c.mkdir(parents=True, exist_ok=True)
        print(f"📁 Proof mode ON → {folder_c}")
    else:
        print("⚡ Proof mode OFF")

    # =========================
    # CPU CORE ALLOCATION (-3 cores default)
    # =========================
    cpu = os.cpu_count() or 4
    workers = args.workers or max(1, cpu - 3)

    print(f"⚡ Using {workers} worker threads (CPU cores - 3)\n")

    files_a = collect(folder_a)
    files_b = collect(folder_b)
    all_files = files_a + files_b

    seen = {}
    group = 1

    # =========================
    # MULTICORE HASHING
    # =========================
    print("⚡ Hashing files (multicore)...")

    results = {}

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker_hash, f) for f in all_files]

        for future in as_completed(futures):
            file_path, h = future.result()
            results[file_path] = h

    # =========================
    # DEDUPE PASS
    # =========================
    print("\n--- DEDUPING ---\n")

    for f in files_a:
        h = results.get(f)
        if not h:
            continue

        if h not in seen:
            seen[h] = ("A", f)
        else:
            if proof and folder_c:
                print(f"📋 DUP A → {Path(f).name}")

                shutil.copy2(f, safe_path(folder_c, f"{group}{Path(f).suffix}"))
                shutil.copy2(seen[h][1], safe_path(folder_c, f"{group} (dupe){Path(f).suffix}"))

                group += 1

    for f in files_b:
        h = results.get(f)
        if not h:
            continue

        matched = False

        for existing_h, (origin, original) in seen.items():
            if is_duplicate(h, existing_h):
                matched = True

                if proof and folder_c:
                    print(f"📦 DUP B → {Path(f).name}")

                    shutil.move(f, safe_path(folder_c, f"{group}{Path(f).suffix}"))

                    if origin == "A":
                        shutil.copy2(
                            original,
                            safe_path(folder_c, f"{group} (dupe){Path(original).suffix}")
                        )

                    group += 1
                else:
                    shutil.move(f, folder_b / Path(f).name)

                break

        if not matched:
            seen[h] = ("B", f)

    print("\n========================")
    print(f"Groups: {group - 1}")
    print("========================\n")


if __name__ == "__main__":
    main()