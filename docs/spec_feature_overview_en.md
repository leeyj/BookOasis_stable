# 📑 BookOasis Core Feature Specifications

This document outlines the core technological designs, architectural specifications, and implementation details that drive BookOasis's lightweight, high-performance media server.

---

## 1. Offset-Based Real-Time Archive Streaming Viewer

### 💡 Overview
Traditional comic/book web viewers extract the entire ZIP/CBZ archive to a temporary server directory when serving a request. This causes massive disk I/O bottlenecks and excessive memory overhead. BookOasis utilizes an **on-the-fly streaming architecture** that slices exact image bytes directly from the archive file channel without extracting the archive.

### 🛠️ Implementation Mechanism
1. **Scanning Phase**: When scanning a ZIP/CBZ file, the scanner parses the central directory structure to capture the **local header byte offset (`local_header_offset`)**, **compressed size (`compress_size`)**, **uncompressed size (`file_size`)**, and compression method of each individual image file. These are pre-indexed into the `book_offsets` table.
2. **Request Phase**: When a client requests a page, the `/api/media/stream` router is invoked.
3. **Streaming Phase**:
   - The server resolves the target page's offset structure from the database in less than a millisecond.
   - It opens the target archive file and seeks directly using `f.seek(local_header_offset)`.
   - It reads only the specified byte length, decompresses it on-the-fly in memory, and returns the binary image stream.
   - **Result**: Even 1GB+ files complete page loading in under 10ms with minimal memory footprint on the host.

---

## 2. Frontend Optimizations (Preloading & Lazy Loading)

### 💡 Overview
A rendering pipeline designed to maintain a smooth 60fps and eliminate loading latency (buffering) when scrolling through a library containing tens of thousands of books.

### 🛠️ Implementation Mechanism
* **Intersection Observer-Based Lazy Loading**:
   - Image cards outside the viewport remain as lightweight placeholders. Thumbnails are requested dynamically only when they enter the viewport, saving network bandwidth and browser connection pools.
* **Viewport-Margin Preloading**:
   - As the user reads a book, the next and previous pages are prefetched silently in the background, minimizing page transition latency to zero.
* **Batch DOM Injection via DocumentFragment**:
   - Instead of inserting nodes one-by-one (which causes constant rendering reflows), card grids are built inside an in-memory `DocumentFragment` and injected into the DOM in a single layout paint.

---

## 3. Dynamic Metadata Plugin Architecture & Config Isolation

### 💡 Overview
An extensible plugin framework designed to decouple the core application from third-party metadata providers (e.g., Aladin Open API).

### 🛠️ Implementation Mechanism
* **Standardized `MetadataPlugin` Interface**:
   - Defines standard methods such as `search_books()` and `get_book_detail()` to enforce unified plugin contracts.
* **Dynamic Loading & Configuration Storage**:
   - Plugin scripts defined under `plugins/` are dynamically loaded at startup and exposed in the admin control panel.
   - Individual plugins can define their own `Config Schema` (such as API keys), which are stored safely in the database (`settings` table).
* **Manual Metadata Retrieval & Bulk Propagation**:
   - From the detail page, users can query active plugins to retrieve information and override the Title, Author, Description, and high-resolution Covers.
   - The selected text metadata can be propagated to all volumes within the same series with a single click.

---

## 4. Security, Granular Permissions, and OPDS Integration

### 💡 Overview
Protects library content against unauthorized access while maintaining standard compatibility for external mobile e-readers.

### 🛠️ Implementation Mechanism
* **Privilege Separation**:
   - Session-based filters (`login_required`) protect all media APIs from anonymous access.
   - Streaming endpoints for adult-categorized libraries validate the user's `has_adult_access` permission flag, returning `403 Forbidden` if unauthorized.
* **[NEW] Granular Category-Level Permissions**:
   - Admins can map and toggle access to specific library categories on a per-user basis. These permissions are stored in the `user_category_permissions` table.
* **OPDS (Open Publication Distribution System) Integration**:
   - Implements XML feed APIs (`/opds`, `/opds-adult`) for integration with mobile readers.
   - Specifically supports **`/app-opds`** and **`/app-opds-adult`** endpoints designed for seamless integration with **Tachiyomi** and **Mihon**.
   - Secures communication using **HTTP Basic Authentication** to validate credentials against the database.

---

## 5. [NEW] Mobile Responsive Design & Solid 4-Tier Architecture

### 💡 Overview
Ensures robust rendering performance across multiple mobile form-factors and maintains infrastructure agility for scale-out setups.

### 🛠️ Implementation Mechanism
* **Notch & Safe Area Padding Support**:
   - Leverages CSS `env(safe-area-inset-top)` and `env(safe-area-inset-bottom)` inside modals and viewports to prevent content clipping on notch-style displays. Explicitly overrides WebKit absolute rendering issues using `height: 100% !important;` to ensure layout integrity on iOS Safari/Chrome.
* **Safe Multilingual (i18n) innerHTML Rendering**:
   - Detects markup tags (e.g., `<strong>`) inside translated resources and securely renders them without exposing raw string codes.
* **4-Tier Clean Architecture Separation**:
   - Decoupled SQL queries from routes/services into designated repositories: `UserRepository`, `CategoryRepository`, and `SettingsRepository`. This allows for seamless transitions to other database systems (e.g., PostgreSQL or MariaDB).
   - System maintenance routines (SQLite `REINDEX`, `VACUUM`, and database statistics updates) are isolated into a dedicated service layer (`db_tuning_service.py`).

---

## 6. [NEW] User Custom Shortcuts & Global Console Log Suppression

### 💡 Overview
Provides dynamic shortcut recording to avoid system-level key collisions (especially in Linux desktop environments) and optimizes production performance by silencing chatty browser debug logs.

### 🛠️ Implementation Mechanism
* **Browser-level keydown Shortcut Recorder**:
   - Integrates a key capturing panel inside the settings page (`general_tab.html`). Users can record their modifier keys (Ctrl/Alt/Shift) along with character keys, storing the serialized JSON string directly in LocalStorage.
* **Instant keydown Hooking**:
   - To bypass module closure constraints and delay, the global event listener dynamically parses LocalStorage on keydown events to compare keycodes in real-time, providing instant shortcut updates without requiring a page refresh.
* **VIEW_LOG Env-based Global Monkey Patch**:
   - Flask reads `VIEW_LOG` from `.env` and passes it to the frontend via index.html templates. If not set to `true`, a global monkey patch replaces `console.log` and `console.warn` with empty functions, reducing rendering overhead. `console.error` remains intact for diagnostic tracking.
