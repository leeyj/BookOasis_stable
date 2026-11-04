[한국어](guide_install_synology.md)

# Installing on a Synology NAS (Container Manager)

Install from the NAS web interface by **pasting one settings file** — no terminal, no git. (About 15 minutes)

> **What was verified**: the compose content and the path/permission behavior below were run as-is on Docker (Ubuntu) (2026-11-03).
> DSM menu names and order were not checked on a real Synology. If your screens differ, please tell the community.

---

## 0. Know this first: there are two paths

BookOasis runs inside a "small box" (a container) on the NAS. Inside the box, NAS folders appear under **a different name**.

| Path on the NAS | Path inside BookOasis (the box) |
|---|---|
| `/volume1/books` | `/data/books` |

You set this link with one line in the settings below. Later, when creating a category in BookOasis, enter the **right-hand path (`/data/books`)**. Entering the NAS path gives "the path does not exist on the server or has a typo" — the most common mistake.

---

## 1. Install Container Manager

**Package Center** → search `Container Manager` → **Install**

---

## 2. Create folders

In **File Station**, create these folders inside the `docker` shared folder (created when Container Manager is installed):

```
docker/
  bookoasis/
    db/
    covers/
    cache/
    tts_audio/
    plugins/
```

> Container Manager may stop with an error when a linked folder does not exist, so create them first.

Also note the path of your book folder: right-click it in File Station → **Properties** → the location shows `/volume1/…`.

---

## 3. Create the project (paste the settings)

**Container Manager → Project → Create**

- Project name: `bookoasis`
- Path: the `docker/bookoasis` folder from step 2
- Source: **Create docker-compose.yml**

Paste all of this and change **only the two marked places**.

```yaml
services:
  bookoasis:
    image: ghcr.io/leeyj/bookoasis:stable
    container_name: bookoasis
    restart: unless-stopped
    stop_grace_period: 1m
    ports:
      - "5930:5930"
    environment:
      - SECRET_KEY=change-me-to-any-long-random-sentence-2026   # ① change to any long sentence
      - TZ=Asia/Seoul
      - REDIS_URL=redis://redis:6379/0
      # - PUID=1026   # (optional) see "Permissions" below
      # - PGID=100
    volumes:
      - ./db:/app/db
      - ./covers:/app/covers
      - ./cache:/app/cache
      - ./tts_audio:/app/tts_audio
      - ./plugins:/app/plugins
      - /volume1/books:/data/books:ro   # ② change only the left side to your book folder
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    container_name: bookoasis_redis
    restart: unless-stopped
```

- **① SECRET_KEY**: the key that keeps you signed in. Any long sentence of letters and numbers. If left empty, everyone is signed out every time the NAS restarts.
- **② Book folder**: change only the part **left** of the colon (`:`) to your NAS path. Keep `/data/books` and the trailing `:ro` (read-only).
  Several book folders? Add lines:
  ```yaml
      - /volume1/comics:/data/comics:ro
      - /volume1/novels:/data/novels:ro
  ```
  Set `TZ` to your time zone (e.g. `Europe/Berlin`).

**Next** → skip the web portal settings → **Done**. The first start takes a few minutes to download the image.

**Success**: two containers, `bookoasis` and `bookoasis_redis`, are **running**.

---

## 4. Open it and change the password

In a browser: `http://NAS-address:5930` (e.g. `http://192.168.0.10:5930`)

- First account: `admin` / `admin`
- After signing in, **the password change screen comes first.** Nothing else works until you change it.

---

## 5. Create your first category

**Add category** → path **`/data/books`** (the right side of ② in step 3) → save

When books appear, you are done. 🎉

---

## Permissions (PUID / PGID) — optional

**If you use the settings as given, you can ignore this.** By default BookOasis can read all NAS folders.

To run BookOasis only with a specific NAS user's permissions, remove the `#` from the `PUID`/`PGID` lines and enter that user's numbers.

- Finding the numbers: **Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script**, pick the user, command `id` → in the result (email notice or log) read `uid=…`, `gid=…`
  (If you use SSH: `id USERNAME`)
- **That user must have read permission on the book shared folder.** (Control Panel → Shared Folder → Edit → Permissions)

> Without permission, **the category is created with no error but shows 0 books.** The screen gives no reason; only the log shows `Permission denied: '/data/books'`. (Reproduced.) Grant permission, or comment the PUID/PGID lines out again with `#` and restart the project.

---

## Updating (screen order needs community confirmation)

**Container Manager → Project → bookoasis → Action → Build** (downloads the image again and recreates). Or, if **Image** shows an update for `ghcr.io/leeyj/bookoasis`, update it and restart the project.

Your data (`db`, `covers`, …) lives in the step 2 folders and survives updates.

---

## Common problems

| Symptom | Cause → fix |
|---|---|
| "does not exist on the server or has a typo" when adding a category | entered the NAS path (`/volume1/…`) → enter the right-hand path such as **`/data/books`** |
| Category created but 0 books | PUID/PGID user has no read permission on the book folder → "Permissions" above |
| Bind mount / path error when creating the project | step 2 folders missing, or a typo on the left side of ② |
| Port `5930` already in use | change only the left side of `ports:` (e.g. `"5940:5930"`) and open `http://NAS-address:5940` |
| Signed out after every NAS restart | ① SECRET_KEY empty or changing → set a fixed sentence |
| Want access from the internet | prefer Tailscale or DSM reverse proxy + HTTPS over opening router ports ([installation guide §4](guide_installation_en.md)) |

To connect books on Google Drive, see [Connecting Google Drive (rclone)](guide_rclone_gdrive_en.md).

---

Related: [Oracle free server install](guide_install_oracle_en.md) · [Connecting Google Drive (rclone)](guide_rclone_gdrive_en.md) · [Installation guide](guide_installation_en.md)
