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
* **Is Adult**: When checked, the library is only revealed to accounts with the adult authentication flag assigned.
* **VFS Refresh before scan**: Specifies whether to call the Rclone API to refresh the cache right before scanning to sync the latest remote drive state.

---

## 4. Library Scanner Control

The Scanner is the core engine that synchronizes the file system and database in a background thread.

* **Scan All**: Integrates and executes the addition of new books, path movements, and removal of deleted books in the specified library.
* **Covers Only**: Skips metadata parsing or offset extraction and targets only missing or corrupted cover images (Cover) for rapid extraction/generation.
* **Cancel**: If you press the 'Cancel' button while a scan task is running, the scanner safely finishes processing up to the current folder unit and then voluntarily terminates the task.
* **Checkpoint Mechanism**: Even if an error or forced termination occurs during a scan, the records of already completed folders remain intact in `scanner_progress`, so the next scan will automatically resume from the remaining parts.

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
