---
title: "CLI Category Export/Import Tool Guide (Native & Docker Fully Supported)"
category: "guide"
date: 2026-07-23
tags: [cli, export, import, migration, backup, multi-path, batch, zip_stored, docker, inspect]
---

# 📦 Category Export/Import CLI Tool Guide (`export_category.py` / `import_category.py`)

This standalone CLI utility allows you to ultra-fast migrate all database metadata (`series`, `books`, `book_offsets`) and cover image files of a category to another system or backup repository without needing external metadata re-searches (Aladin/Naver) or viewer streaming offset recalculations.

**Fully supports both Native environments and Docker (Docker / Docker-Compose) environments, along with multi-path (Multi-path) directory mappings and batch exports.**

---

## 🔍 0. Pre-Import Package Inspection (`--info` / `--inspect`)

Before running the import command, you can inspect the `.oasis.zip` package to check **how many physical directory paths were in the original category and their exact path structures**.

```bash
# Native Environment
python tools/import_category.py -i package_file.oasis.zip --info

# Docker Environment
docker exec -it bookoasis python tools/import_category.py -i /app/covers/package_file.oasis.zip --info
```

### **Inspection Report Output Example**:
```text
==========================================================
📦 [BookOasis Package Inspection Info]
==========================================================
  • Category Name : Home_Living(GDS)
  • DB Type       : general
  • Total Books   : 2351 items
  • Total Covers  : 2351 files
  • Original Physical Paths Count : 2 entries
    [0] /home/az001a/google/GDRIVE/READING/Books/YES24/Living
    [1] /home/az001a/google/GDRIVE/READING/Books/RidiSelect/Life
==========================================================
👉 Import Recommendation:
   Please provide 2 target path(s) (-p) when importing this package!
==========================================================
```

---

## ⚡ Packaging Performance Optimization (`ZIP_STORED`)
- Re-compressing already compressed image binaries (WebP, JPG, PNG) yields 0% size reduction and consumes unnecessary CPU time.
- Therefore, we utilize **`zipfile.ZIP_STORED` (uncompressed store)** mode.
- Results in **0% CPU load** and completes archiving in seconds at raw disk I/O bandwidth speeds.

---

## 💻 1. Native Environment Usage Guide

### **A) Category Export (`export_category.py`)**
```bash
# Export single category
python tools/export_category.py --db general -l 21

# Batch export multiple categories at once
python tools/export_category.py --db general -l 15 18 21 -o /backups/
```

### **B) Category Import (`import_category.py`)**
```bash
# Single physical path import
python tools/import_category.py -i /backups/manga_21.oasis.zip -p "/volume1/mnt/GDDRIVE/READING/Manga/Completed"

# Multi-path category import (No limit on -p flags: 2, 5, 8, etc.)
python tools/import_category.py \
  --input /backups/novel_export.oasis.zip \
  --target-path "/volume1/mnt/GDRIVE/READING/Books/YES24/Living" \
  --target-path "/volume1/mnt/GDRIVE/READING/Books/RidiSelect/Life" \
  --name "Home_Living(GDS)"
```

---

## 🐳 2. Docker (Docker / Docker Compose) Environment Usage Guide

Even if Python is not installed on the host OS, you can run the scripts immediately inside the active BookOasis container using `docker exec`.

> [!TIP]
> **💡 Key Formula to Avoid Confusion for Docker Users**:
> `[Server Physical Path in Web UI Category Management] <─── 100% Identical ───> [-p Option Path]`
> 
> **Example**: If the server physical path configured in the Web UI is `"/volume1/mnt/GDDRIVE/READING/Manga/Completed"`, simply pass `"/volume1/mnt/GDDRIVE/READING/Manga/Completed"` as the `-p` parameter!

### **A) Docker Environment Export**
Specify an output path shared with the host volume (e.g. `/app/covers`) to generate the backup package on the host filesystem.

```bash
# 1) Using Docker (assuming container name: bookoasis)
docker exec -it bookoasis python tools/export_category.py --db general -l 21 -o /app/covers/manga_21.oasis.zip

# 2) Using Docker Compose
docker-compose exec bookoasis python tools/export_category.py --db general -l 21 -o /app/covers/manga_21.oasis.zip
```

### **B) Docker Environment Import**
Use the container-internal physical path (identical to the Web UI setting) for `-p`. You can repeat the `-p` flag as many times as needed for multi-path categories without any quantity limits.

#### **1) Single Physical Path Import Example**
```bash
# Using Docker
docker exec -it bookoasis python tools/import_category.py \
  -i /app/covers/manga_21.oasis.zip \
  -p "/volume1/mnt/GDDRIVE/READING/Manga/Completed" \
  -n "Imported Manga"

# Using Docker Compose
docker-compose exec bookoasis python tools/import_category.py \
  -i /app/covers/manga_21.oasis.zip \
  -p "/volume1/mnt/GDDRIVE/READING/Manga/Completed" \
  -n "Imported Manga"
```

#### **2) Multi-Path Import Example (Multiple -p flags, unlimited: 2, 5, 8, etc.)**
```bash
# Using Docker
docker exec -it bookoasis python tools/import_category.py \
  -i /app/covers/novel_export.oasis.zip \
  -p "/volume1/mnt/GDRIVE/READING/Books/YES24/Living" \
  -p "/volume1/mnt/GDRIVE/READING/Books/RidiSelect/Life" \
  -n "Home_Living(GDS)"

# Using Docker Compose
docker-compose exec bookoasis python tools/import_category.py \
  -i /app/covers/novel_export.oasis.zip \
  -p "/volume1/mnt/GDRIVE/READING/Books/YES24/Living" \
  -p "/volume1/mnt/GDRIVE/READING/Books/RidiSelect/Life" \
  -n "Home_Living(GDS)"
```

---

## 🔒 Key Feature Summary
1. **Package Pre-Inspection (`--info`)**: Verify original path structures, counts, and book totals before restoring to DB.
2. **Native & Docker Support**: Seamlessly executes via `docker exec` in various infrastructure setups.
3. **Ultra-Fast `ZIP_STORED` Packaging**: Bypasses image re-compression for 0% CPU usage and sub-second archiving.
4. **Collision-Proof Filenames**: Automatically generates `{CategoryName}_{db_type}_lib{ID}_{YYYYMMDD_HHMMSS}.oasis.zip`.
5. **100% 1:1 Multi-Path Restoration**: Maps N physical paths (2, 5, 8, etc.) 1:1 to new target paths based on original `root_index`.
