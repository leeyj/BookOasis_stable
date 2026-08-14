---
title: "Admin Guide"
project: "BookOasis"
category: "guide"
date: 2026-06-22
tags: [admin, guide, management]
---

# 👑 BookOasis Administrator Guide

This document is a dedicated manual for Administrators to manage and optimize the BookOasis system.

---

## 1. Account Hierarchy & Privilege Isolation

BookOasis supports a multi-user environment where access scopes are isolated based on account levels.

| Account Role | Accessible Areas | Description |
| :--- | :--- | :--- |
| **Admin** | Entire system (Dashboard, Viewer, Settings, Scanner Control, User Management) | The highest-level account capable of controlling the system's physical resources and all detailed settings. |
| **User** | Viewing book lists and reading on the media viewer | Can only consume content and cannot access admin menus such as settings or scanner controls. |

> [!WARNING]
> For Adult Libraries containing adult comics/novels, only accounts with the **'Is Adult'** flag set to True (`1`) are permitted to access and view them.

---

## 2. User Management (Users Tab)

Administrators can control system access privileges via the **[Settings Icon ⚙️] -> [User Management]** tab.

### ① Registering Users
* Enter the Username and Password for the new user, check their Role (Admin/User) and Adult Status (Is Adult), and then register.
* Passwords are securely hashed before being stored in the database.

### ② Deleting Users
* You can instantly revoke privileges by clicking the 'Delete' button on the right side of the registered user list.
* Self-deletion (for the currently logged-in admin account) is prohibited to prevent accidental loss of system management privileges.

### ③ Category-specific Permission Control (Permissions Tab)
* Administrators can individually control the library categories that specific users can access through the **[Settings Icon ⚙️] -> [Permissions Management]** tab.
* A grid-style table displays all users mapped against the available categories. Toggling the switches on or off instantly grants or revokes access to the corresponding library.
* Regular users (User role) will only see series and books from categories for which they have been granted access (`has_access = 1`) on the main dashboard, sidebar, and OPDS clients.

---

## 3. Library (Category) Setup

A Library is a unit that binds books in a physical directory to a specific library category on the Web UI.

### ① Add Library Fields
* **Library Name**: The name displayed on the Web UI sidebar.
* **Target Physical Path**: The absolute path on the server where the book files are stored (e.g., `D:\Manga` or `/home/user/books`).
* **Is Remote**: Check this if it's a remote storage like Google Drive mounted via Rclone VFS.
  * *When checked: Skips detailed offset analysis inside compressed files and automatic temporary cover extraction to prevent network bottlenecks.*
  * *When unchecked: the scanner will not attempt remote VFS refreshes (RC / `vfs/refresh`) during scans.*
* **Is Adult**: When checked, the library is only revealed to accounts with the adult authentication flag assigned.
* **VFS Refresh before scan**: Specifies whether to call the Rclone API to refresh the cache right before scanning to sync the latest remote drive state.

---

## 4. Library Scanner Control

The Scanner is the core engine that synchronizes the file system and database through a queue-backed background worker process.

* **Scan All**: Integrates and executes the addition of new books, path movements, and removal of deleted books in the specified library.
* **Covers Only**: Skips metadata parsing or offset extraction and targets only missing or corrupted cover images (Cover) for rapid extraction/generation.
* **Cancel**: If you press the 'Cancel' button while a scan task is running, the scanner safely finishes processing up to the current folder unit and then voluntarily terminates the task.
* **Checkpoint Mechanism**: Even if an error or forced termination occurs during a scan, the records of already completed folders remain intact in `scanner_progress`, so the next scan will automatically resume from the remaining parts.

### ⑤ Scan Ignore Patterns & .bookoasisignore Setup
You can exclude specific files or directories from being scanned, such as Synology NAS thumbnail folders (`@eaDir/`), recycle bins (`#recycle/`), or temporary files (`*.tmp`, `*.sample.cbz`).

* **Global Ignore Patterns (Admin Settings)**:
  - Enter patterns line by line under **[Settings ⚙️] -> [General Settings] -> "Scan Ignore Patterns"**.
  - **Directory Patterns**: Must end with `/` (e.g., `@eaDir/`, `#recycle/`, `.git/`, `.svn/`).
  - **File Patterns**: Enter filenames with wildcards (e.g., `*.tmp`, `*.sample.cbz`, `Thumbs.db`, `.DS_Store`, `desktop.ini`).
* **Per-Folder Custom Setup (`.bookoasisignore`)**:
  - Place a `.bookoasisignore` file inside a specific directory to apply custom ignore rules to that folder and its subdirectories.
* **Scan Logs & Trash Synchronization**:
  - Excluded directories are immediately blocked from physical subfolder traversal and explicitly logged in `media_server.log` (`[Scanner-Ignore]`).
  - Previously registered items that become ignored are safely moved to the Trash (Soft Delete).

---

## 5. System and Plugin Setup

### ① Metadata Plugins (Aladin, etc.)
* **Dynamic API Key Registration**: Through the latest plugin architecture, you can easily turn on/off various external book info integration plugins like Aladin (TTBKey), Google Books, Amazon, etc., and manage API keys dynamically from the settings tab.
* Activated plugins will appear as selection options during manual metadata searches on individual book detail modals, allowing you to merge accurate metadata (author, publisher, description, high-quality cover, etc.) with a single click.

### ② System Scroll and Thumbnail Specification Settings
* **Thumbnail Width and Scroll Caching**: You can dynamically adjust the thumbnail resolution specifications from the settings tab to optimize performance.

---

## 6. Scan Error Reports

During a scan, damaged compressed files (Bad Zip File), corrupted images, or unreadable file info due to permission issues are not deleted or omitted but are archived in the **[Scan Error Report]**.

* Administrators can view the error reports to pinpoint exactly which files are broken on the physical drive. After resolving the issues, they can initialize the list by 'Deleting All' reports.

---

## 7. Adding Custom Fonts (User Fonts)

You can add custom fonts to be used in the web viewer (TXT/EPUB).

* **Supported Formats**: `.ttf`, `.otf`, `.woff`, `.woff2`
* **How to Add**:
  1. Go to the `static/fonts/custom/` folder inside your server installation path (create it if it doesn't exist).
  2. Copy your font files into the directory above.
  3. Connect to BookOasis in your browser, open the reader, click font settings (A), and select your font from the dropdown list.

---

## 8. Database Administration & MariaDB Migration

BookOasis officially supports **MariaDB / MySQL Enterprise Mode** alongside built-in SQLite.

### ① SQLite vs MariaDB Selection Guide
* **SQLite (Default)**: Embedded single-file DB. No installation required. Ideal for small-scale & single-user environments.
* **MariaDB / MySQL (Recommended)**: Eliminates disk lock bottlenecks and corruption risks in high-concurrency / large library (tens to hundreds of thousands of books) setups.

### ② MariaDB Setup (.env)
```env
DB_ENGINE=mariadb
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mariadb_password
```

### ③ SQLite -> MariaDB One-Click Migration Tool
Migrate all existing SQLite data (metadata, reading history, user permissions) to MariaDB with zero data loss:
```bash
python tools/migrator_sqlite_to_mariadb.py
```
* **How to Add**:
  1. Navigate to the `static/fonts/custom/` directory within your server's installation path. (Create the directory if it does not exist.)
  2. Upload (or copy) your font files into this directory.
  3. Access BookOasis in your browser, open the viewer, and check the font selection dropdown. The newly added fonts will automatically appear in the list.

### ④ MariaDB Performance Tuning: innodb_buffer_pool_size
The official MariaDB image defaults `innodb_buffer_pool_size` to just **128MB**. As your library grows (tens of thousands of books or more), a buffer pool smaller than your actual data size forces repeated disk I/O on every query, causing statistics/diagnostic queries to become abnormally slow.

* **Recommended value**: Set it to at least the combined size of `media_general` + `media_adult` + `media_audiobook`, within your available RAM (`docker-compose.mariadb.yml` defaults to `2G`).
* **Docker Compose deployments**: For large libraries needing more than the `2G` default, don't edit `docker-compose.mariadb.yml` directly — copy `docker-compose.override.mariadb.example.yml` as an override instead. (See the "MariaDB + Redis Combo Mode" section of the installation guide.)
* **Native (non-Docker) MariaDB**: Add the following to the `[mysqld]` section of `/etc/mysql/mariadb.conf.d/50-server.cnf` (path may vary by distro), then restart with `systemctl restart mariadb`:
  ```ini
  innodb_buffer_pool_size = 2G
  ```
* **Verify**:
  ```sql
  SHOW VARIABLES LIKE 'innodb_buffer_pool_size';
  ```
