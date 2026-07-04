# 🏗️ BookOasis Architecture and Layered Structure Guide (Architecture Guide)

This document describes the architectural design of the BookOasis media server, the roles of each source code layer, key classes and functions, and the flow of data in detail.

---

## 1. Architecture Overview

BookOasis adopts a **4-tier layered architecture (Layered Architecture)** to maximize the separation of concerns (SoC).

* The **Route (Controller)** layer handles incoming requests and parameters validation.
* The **Service** layer executes rich domain business logic.
* The **Repository** layer encapsulates direct query (SQL) processing to the database.
* The **Data (Infrastructure)** layer controls physical database sessions and drive mounts.

```mermaid
graph TD
    Client[Web Browser / OPDS Client]
    
    subgraph Route_Layer [1. Route Layer Blueprints]
        AuthRoute[api/auth.py]
        LibRoute[api/library.py]
        StreamRoute[api/stream.py]
        OpdsRoute[api/opds.py]
        AdminRoute[api/admin.py]
    end

    subgraph Service_Layer [2. Service Layer Services]
        BookService[services/book_service.py]
        StreamService[services/stream_service.py]
        MetaService[services/metadata_service.py]
        DetailService[services/book_detail_service.py]
        HistoryService[services/reading_history_service.py]
        CategoryService[services/category_service.py]
        SettingsService[services/settings_service.py]
        TuningService[services/db_tuning_service.py]
    end

    subgraph Repository_Layer [3. Repository Layer Repositories]
        UserRepo[repositories/user_repository.py]
        CategoryRepo[repositories/category_repository.py]
        SettingsRepo[repositories/settings_repository.py]
    end

    subgraph Infrastructure_Layer [4. Infrastructure & Data Layer]
        DB[database.py SQLite Pool]
        Rclone[utils/drive_helper.py VFS]
        Pillow[utils/cover_helper.py WebP]
    end

    Client --> Route_Layer
    Route_Layer --> Service_Layer
    Service_Layer --> Repository_Layer
    Repository_Layer --> Infrastructure_Layer
```

---

## 2. Layer Details

### 📌 1) Route Layer
Receives HTTP requests from clients, validates parameters, and triggers appropriate service methods. It is separated into the `api/` and `api/routes/` directories.
* **`api/auth.py` (Authentication)**: Controls login processing, password changes, and user account creation and deletion.
* **`api/routes/library_routes.py` (Library Control)**: Handles administrator controls such as library creation, metadata modification, and scheduling settings.
* **`api/routes/system_routes.py` (System Router)**: Renders the web page index (`/`) and returns `/health` check API responses.

### 📌 2) Service Layer
A layer of pure Python modules where actual domain business logic and workflow coordination are concentrated.
* **`services/db_tuning_service.py` (`db_tuning_service`)**: A system tuning service that manages SQLite physical defragmentation (`VACUUM`), updates database statistics (`ANALYZE`), and rebuilds index structures (`REINDEX`).
* **`services/settings_service.py` (`SettingsService`)**: Handles the business logic for retrieving setting values and writing/syncing them to both databases (`general` and `adult`).
* **`services/category_service.py` (`CategoryService`)**: Coordinates adding/editing categories and returning category lists filtered by user permissions.

### 📌 3) Repository Layer
A layer that isolates SQL query statements to lower the architectural coupling. Located in the `repositories/` directory.
* **`repositories/user_repository.py` (`UserRepository`)**: Encapsulates all CRUD SQL queries for the `users` and `user_category_permissions` tables.
* **`repositories/category_repository.py` (`CategoryRepository`)**: Manages SQL operations for the `libraries` table, including category CRUD and cron schedule updates.
* **`repositories/settings_repository.py` (`SettingsRepository`)**: Handles SQL queries to read and write values in the `settings` table.

---

## 3. Core Data Flow

### 🔄 User Creation and Permission Seeding Flow

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Admin (Web Browser)
    participant Route as api/auth.py (add_user)
    participant Repo as repositories/user_repository.py
    participant DB as SQLite (media_general.db)

    Admin->>Route: Add User Request (POST /api/admin/users)
    Route->>Route: Validate inputs and hash password
    Route->>Repo: add_user(db_type, username, hashed_pw, role)
    Repo->>DB: INSERT INTO users
    Repo->>DB: SELECT id FROM libraries (Collect all categories)
    Repo->>DB: INSERT INTO user_category_permissions (Seed default access = 1)
    DB-->>Repo: Commit Transaction
    Repo-->>Route: Return Created User ID
    Route-->>Admin: Return JSON (Success)
```
