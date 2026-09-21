---
title: "MCP Server Guide"
project: "BookOasis"
category: "guide"
date: 2026-09-15
tags: [mcp, ai, claude, guide]
---

# 🤖 BookOasis MCP Server Guide

As a library grows into the tens or hundreds of thousands of books, manually tracking data-quality issues (missing covers/genre/tags, series scattered as duplicates across categories) becomes practically impossible. BookOasis ships a **read-only MCP (Model Context Protocol) server**, so any MCP-capable AI coding tool (Claude Code, Claude Desktop, Gemini CLI, OpenAI Codex CLI, Cursor, etc. — MCP is an open standard, not tied to any one vendor) can query your library directly and surface problems to you.

- Transport is **local stdio only** — never exposed over the network. The AI tool runs the `tools/mcp_server.py` process directly on the same machine where BookOasis is installed. No extra authentication setup needed.
- v1 shipped read-only diagnostic tools only. Starting with v1.1, **low-risk (Tier A) write tools** shipped, followed shortly after by the **Tier B propose-then-approve queue** for bulk operations; both are off by default and an admin must explicitly enable them (see the "Write tools" section below).
- Install the `mcp` package first with `pip install -r requirements.txt`. Registration steps below are per-client — skip the ones you don't use.

## Registration

### Common — the MCP server definition (JSON)

Nearly every MCP client ultimately registers a server with a JSON block shaped like this; only the config file's name/location differs between clients.

```json
{
  "mcpServers": {
    "bookoasis": {
      "command": "python3",
      "args": ["/path/to/media_server/tools/mcp_server.py"]
    }
  }
}
```

Replace `/path/to/media_server` with your actual BookOasis install path (absolute path).

### Claude Code

```bash
claude mcp add bookoasis -- python3 /path/to/media_server/tools/mcp_server.py
```

Confirm with `claude mcp list` — it should show `✔ Connected`.

### Claude Desktop

Open `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`), add the "common JSON" block above under `mcpServers`, and restart the app.

### Docker installs

Docker deployments usually only have `python3` inside the container, not on the host, so registering `claude mcp add` with the plain host command will fail. Register it to run `mcp_server.py` inside the container via `docker exec` instead — no image changes needed (`mcp` is already installed at build time via `requirements.txt`).

```bash
claude mcp add bookoasis -- docker exec -i bookoasis python3 tools/mcp_server.py
```

- `bookoasis` is the container name in the default `docker-compose.yml`. If you renamed it or run multiple instances (`bookoasis_test`, etc.), check the real name with `docker ps` and substitute it.
- **`-i` is required** (it keeps stdin open so the MCP client can pipe JSON-RPC messages into the container). **Never add `-t`** — attaching a TTY mixes terminal control characters into the stream and breaks the stdio protocol.
- The container obviously has to be running for the connection to work — same requirement as the BookOasis web UI itself being up.
- As a common JSON block (for Claude Desktop etc.):
  ```json
  {
    "mcpServers": {
      "bookoasis": {
        "command": "docker",
        "args": ["exec", "-i", "bookoasis", "python3", "tools/mcp_server.py"]
      }
    }
  }
  ```

### Gemini CLI / OpenAI Codex CLI / Cursor / other MCP clients

Most of these also use the same `mcpServers` JSON shape, but the exact config file name/location and any CLI registration command (if one exists) varies by tool and can change over time. Check that tool's current official docs for "register an MCP server" and paste in the common JSON block above — as long as `command`/`args` are correct, it works identically regardless of which client you use.

To inspect the tool list/schema quickly without any client, using the official inspector bundled with the `mcp` package:

```bash
mcp dev tools/mcp_server.py
```

## Available tools

### Read-only

| Tool | Description |
| :--- | :--- |
| `search_books` | Search series by title/series name (genre/tag filters, `sort`: asc/desc/date_desc/date_asc; video excluded) |
| `get_random_book` | Pick one series at random on the server (video excluded) |
| `get_library_stats` | Total and per-category series/book counts |
| `find_missing_cover` | Books with no cover image |
| `find_missing_genre_and_tags` | Books with both genre and tags empty |
| `find_missing_offsets` | zip/cbz books missing their page-offset cache and needing a rescan (remote-mounted files such as rclone/GDrive are automatically excluded) |
| `find_duplicate_series` | Cases where the exact same series name is scattered across 2+ categories |
| `run_readonly_query` | Run raw read-only (SELECT/WITH/EXPLAIN/PRAGMA) SQL against the library DB |
| `read_logs` | Tail the last N lines of a server log under `logs/` (with an optional search filter) |
| `call_api` | Call an existing GET REST API endpoint (`docs/api_endpoints.md`) directly |

### Write (Tier A — low risk, off by default)

| Tool | Description |
| :--- | :--- |
| `update_book_metadata` | Partially update a series' genre/tags/author/publisher/summary/link etc. (fields you omit keep their current value). Rejects `<`/`>` characters and any link that isn't `http(s)://` (see "Input validation" below) |
| `bulk_set_favorite` | Bulk add/remove favorite status for a list of book ids (max 500 per call) |

### Write (Tier B — bulk operations, propose-only, never executes immediately)

| Tool | Description |
| :--- | :--- |
| `propose_bulk_book_metadata_update` | Proposes a bulk metadata update across many series (not applied immediately) |
| `propose_bulk_set_favorite` | Proposes a bulk favorite add/remove for more than 500 books (not applied immediately) |

`find_duplicate_series` only catches exact-name duplicates. For near-duplicates with typos or variant spellings, let Claude explore with `search_books` and judge for itself — that kind of fuzzy-matching judgment call is exactly why you'd hand this off to an AI via MCP in the first place.

### `run_readonly_query` — ask about the schema first if you don't know it

Use this tool for any ad-hoc condition the built-in diagnostic tools don't cover. If you're unsure of the table structure, start with a schema query like `PRAGMA table_info(books)`. Safety is enforced in two layers:

1. **App level**: rejected immediately if the SQL doesn't start with `SELECT`/`WITH`/`EXPLAIN`/`PRAGMA`, contains multiple `;`-separated statements, or contains a write keyword like `INSERT`/`UPDATE`/`DELETE`/`DROP`.
2. **DB level (the real safety net)**: in sqlite mode, every call opens a fresh, genuinely OS-level read-only connection (`file:...?mode=ro`) — even if layer 1 were bypassed, the file physically can't be written to. In MariaDB mode there's no separate read-only account, so the tool wraps the borrowed pooled connection in `SET SESSION TRANSACTION READ ONLY` for the duration of the call and restores it afterward (MariaDB's defense is one notch weaker than sqlite's — there's no plan to add a dedicated read-only DB account, since this is a single-trusted-operator local stdio server to begin with).

### `call_api` — reuse the existing API for anything the diagnostic tools don't cover

Calls an existing GET endpoint documented in `docs/api_endpoints.md`, e.g.:
```
call_api(path="/api/media/list", query_params={"type": "general", "library_id": "all", "limit": 5})
```
- **GET only** — not an app-level filter like the SQL tool's SELECT-only check; this tool's code simply has no way to issue any other HTTP method in the first place.
- Internally it builds a small standalone Flask app and injects an admin session into it (an in-process call, unrelated to the actual running server process — it can't conflict with the live web process). So adult-library / `admin_only` plugin data is reachable without restriction.
- Paths not starting with `/api/` (e.g. `/login`) are rejected.

## Write tools — design principles (Tier A / Tier B)

Once the read-only diagnostic tools proved popular, the natural next ask was "let the AI just fix
what it finds." But an AI agent writing to the library DB — or worse, touching core code or another
plugin — is a real risk, so the scope was deliberately narrowed to the following principles.

1. **Core/plugin source files are never touched.** Write tools do not write to the filesystem at
   all — they only write to the library DB, and only through service/repository methods already
   validated and used by the existing REST API. Schema/DDL changes are out of scope here and always
   will be (`services/db_migration_service.py` remains the sole entry point for those, unchanged).
2. **No general-purpose write-SQL tool.** A tool symmetric to `run_readonly_query` that runs
   arbitrary write SQL is deliberately never provided — that's the core protection. Instead, only
   narrow, purpose-built tools (`update_book_metadata`, `bulk_set_favorite`) are added one at a time.
3. **Two risk tiers.**
   - **Tier A (low risk, executes immediately)**: `update_book_metadata`/`bulk_set_favorite` —
     thin wrappers around existing parameterized service methods, scoped to individual or small
     (≤500) edits, never bulk.
   - **Tier B (bulk operations, propose → approve queue)**: `propose_bulk_book_metadata_update` /
     `propose_bulk_set_favorite` never write to the DB directly — they compute a before/after
     preview and park it in the `mcp_pending_changes` table. An admin reviews it in Settings >
     **MCP Pending Changes** and must click Approve before anything is applied; Reject leaves the
     DB untouched. Triggering rescans / deletions aren't in scope yet — adding either just means
     adding one more `tool_name` branch to the same queue. The admin API this screen uses
     (`GET/POST /api/admin/mcp-pending-changes...`) is documented in `docs/api_endpoints.md` §9.5.
4. **Admin kill switch.** The "Allow MCP write tools" setting (`MCP_WRITE_ENABLED`, off by default,
   under Settings > General) must be explicitly turned on by an admin before any Tier A tool or
   Tier B **proposal creation** will run. Calling one while it's off returns an error. Approving or
   rejecting an *already-created* proposal is a first-party admin action taken from an authenticated
   web session, so it works regardless of this switch — otherwise turning the switch off would leave
   admins unable to clear out a pending queue.
5. **Audit log.** Every write action (Tier A execution, Tier B propose/approve/reject) is recorded
   to `logs/mcp_write_audit.log` with the target and before/after values, viewable anytime via the
   `read_logs` tool (`log_name="mcp_write_audit.log"`). The pending queue itself can also be
   inspected directly with `run_readonly_query('general', 'SELECT * FROM mcp_pending_changes ORDER BY id DESC')`
   — no separate read-only tool was added for it.

### Input validation — closing the "AI-written text executes in the admin's browser" path

While designing the Tier A tools, we specifically asked: what happens if an AI (or a prompt
injection steering one) puts malicious markup into a free-text field like genre/tags/summary?
Auditing where these fields get rendered turned up a **pre-existing stored-XSS vulnerability**
(unrelated to MCP, already there before this feature) in two places — the book detail page header
and the genre/tag filter UI — where these fields were interpolated into `innerHTML` without any
escaping. An admin simply opening that book's detail page would execute the injected script in
their own authenticated browser session, which could then be used to perform any POST action the
admin is allowed to (installing a plugin, changing settings, etc.).

The rendering fix is the real remedy, but since MCP is a new remote write path into these exact
fields, `update_book_metadata` also got defense-in-depth validation:

- Every field rejects `<` and `>` characters outright (blocks HTML tag injection at the source).
- The `link` field is rejected unless it starts with `http://` or `https://` (blocks `javascript:`
  and other dangerous protocols).

The same audit also found the `device` query parameter on `/api/media/videos/check-vaapi`
(reachable via `call_api`) flowing unvalidated into `subprocess`/`os.path.exists()`. It's now
restricted to device node names under `/dev/dri/` (list-form subprocess args already ruled out
shell command injection, but the unvalidated path was still usable as an arbitrary-path-existence
probe).

**Important limitation:** the validation above only stops MCP itself from planting a script. It
does *not* stop an AI from mistaking text a tool *returns* (a book title, a summary, a log line)
for an instruction and attempting a destructive action with one of its *other* tools (e.g. a shell).
That layer of defense belongs to the MCP client's (the AI agent's) own permission/approval model,
not to this server — treat everything these tools return as data, written by anyone with library
access, never as a command.

## `db_type` values

Most tools accept a `db_type` parameter: `general` (general library, default) / `adult` (adult library) / `audiobook`. `video` has a different book-table structure so it isn't a target for the fixed diagnostic tools (`find_missing_*`, `find_duplicate_series`), but `run_readonly_query` allows `video` too.

## Roadmap

- More Tier B action types — the queue currently only supports bulk metadata edits and bulk favorites. Triggering rescans, deletions, etc. just need a new `tool_name` branch in `services/mcp_proposal_service.py`.
- Orphaned-file detection (a DB row exists but the file is gone from disk) — checking existence for every book is slow on remote mounts (rclone/GDrive), so this needs a background job reusing the existing scanner queue plus a separate results-only tool, rather than a synchronous MCP call.
