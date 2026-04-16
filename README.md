# 🧰 Media Dedupe Toolkit

Content-based deduplication toolkit for images and videos across two folders.

---

## 📦 Included Scripts

### 1. `dedupe_short_media_v2.0.py`

Best for:

* Images (`.jpg`, `.png`, `.webp`, etc.)
* GIFs
* Short videos (clips, memes, etc.)

Uses:

* Single-frame perceptual hashing (fast)

---

### 2. `dedupe_long_media_multicore_v3.1.py`

Best for:

* Long videos (`.mp4`, `.mkv`, etc.)
* Mixed media collections

Uses:

* Multi-frame video fingerprinting
* Multicore processing (CPU cores - 3)

---

## ⚙️ Setup

```bash
# Create venv
python -m venv venv

# Activate (PowerShell)
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

---

## ▶️ Usage

### 🔹 CLI Mode

```bash
python dedupe_long_media_multicore_v3.1.py \
  --a "PATH_TO_FOLDER_A" \
  --b "PATH_TO_FOLDER_B" \
  --out "PATH_TO_OUTPUT"
```

### 🔹 Interactive Mode

```bash
python dedupe_long_media_multicore_v3.1.py
```

You’ll be prompted for missing inputs.

---

## 📌 Arguments

| Argument     | Description                             |
| ------------ | --------------------------------------- |
| `--a`        | Folder A (MASTER – never modified)      |
| `--b`        | Folder B (SECONDARY – cleaned)          |
| `--out`      | Output folder (duplicate proof storage) |
| `--no-proof` | Disable output folder usage             |
| `--workers`  | Override CPU worker count               |

---

## 🚨 Core Behavior (IMPORTANT)

* Folder A is treated as the **source of truth**
* Folder B is **cleaned of duplicates**

### If duplicates are found:

* ✅ Folder B file is **REMOVED**
* ✅ Folder A file is **kept**
* ✅ (Optional) Copies are stored in output folder

---

## ✅ Final Result

After running:

* Folder A → unchanged (originals)
* Folder B → only unique files remain
* No duplicate media exists between A and B

---

## 🧠 Detection Method

### Short Media Script

* Perceptual hashing (phash)
* Fast + effective for images & short clips

### Long Media Script

* Multi-frame sampling:

  * start
  * 25%
  * 50%
  * 75%
  * end
* Hash comparison via overlap threshold (~60%)

---

## ⚡ Performance

* Short script → very fast (single frame)
* Long script → heavier but more accurate
* Multicore enabled (v3.1):

  * Default = CPU cores - 3

---

## 📁 Proof Mode (Default)

If enabled:

* Duplicate pairs are saved to output folder
* Files are renamed like:

```
1.mp4
1 (dupe).mp4
```

---

## 🔕 No-Proof Mode

```bash
--no-proof
```

* No output folder needed
* Folder B still gets cleaned
* Faster, but no audit trail

---

## 📦 Supported Formats

### Images

* `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.gif`

### Videos

* `.mp4`, `.mkv`, `.webm`, `.avi`, `.mov`

---

## ⚠️ Notes

* This is **content-based deduplication**

  * Filenames are ignored
* For filename-based dedupe → use a different script
* GIF support is included but lightly tested
* Very long videos may take longer due to frame sampling

---

## 🧪 Recommended Workflow

1. Run `dedupe_short_media_v2.0.py` first
2. Then run `dedupe_long_media_multicore_v3.1.py`
3. Review output folder (if proof mode enabled)

---

## 🧼 Example Use Case

You have:

* Two accounts downloading media from the same site

Goal:

* Merge both collections
* Remove duplicates
* Keep only one copy per media item

This toolkit handles that automatically.

---

## 📄 License

Personal use / internal tooling

---

## 👌 Summary

* ✔ Content-based dedupe
* ✔ Cross-folder comparison
* ✔ Safe (Folder A untouched)
* ✔ Multicore support
* ✔ Proof/audit mode available

---
