# Reader resume regressions

## Dependency-free unit checks

From the repository root, with Node.js 20 or later:

```sh
node --test tests/reader_resume.test.mjs
```

These tests execute the reader's source functions in isolated VM contexts with synthetic DOM/services; they do not boot Flask or simulate browser layout. They cover the scroll coordinate calculation, restoration write guard, user-input release, first-open history, TXT writes, unchanged page-mode geometry, and unchanged legacy EPUB chapter selection. No production data or credentials are needed.

## Actual browser geometry

From the repository root:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/tests/reader_resume.html`. All four results must be `pass: true`, and the page title must start with `PASS`.

The fixture creates a nested EPUB/TXT chapter and a long paragraph containing a saved sentence, at both zero and nonzero initial scroll offsets. It compares the actual sentence Range against the restored container position. The original `paragraph.offsetTop - 30` implementation leaves the sentence offscreen. This fixture uses only the real browser DOM and the actual anchor utility; it does not exercise the whole reader UI or its persistence API.

## Whole-reader manual checks

Use a disposable library and synthetic EPUB/TXT files. Do not use personal books or reading history.

1. **EPUB restore-only:** Read partway through a chapter in scroll mode, close, then reopen. In browser Network, clear the log before reopening and filter to POST `/api/media/progress` and `/api/media/tts/position`. Without reading input, wait longer than the progress debounce and close using the viewer's Close button, Escape, or a tab-visibility change. Restoring the saved viewport must not produce a fresh progress/read POST or advance its local `viewer_last_pos_<id>.savedAt`.
2. **Real reading:** Reopen, scroll with the wheel/touch, or navigate with a key/button. Progress/read POSTs must resume. Close and reopen to confirm persistence.
3. **First-ever EPUB open:** Open a book that has no saved read/listen/local/server position. Its existing first-open progress/history write must still occur.
4. **Page modes:** Verify EPUB two-page and TXT one-page navigation/close still persist. The page-mode anchor calculation is not changed by this patch.
5. **TXT:** Verify scroll-mode sentence restoration and normal progress writes. The EPUB restoration write guard must not block TXT.
6. **TTS:** Start listening with the existing UI and verify its read-position handoff and TTS reporting still work. This patch does not modify TTS synchronization or reporting modules.
7. **Legacy state:** A zero EPUB spine index with a positive percentage must retain its existing percentage fallback. Chapter selection semantics are intentionally outside this patch.

The repository's existing workflow publishes a Docker image on a push to `main` or a tag; it does not run these regressions for a pull request. Run the checks explicitly rather than treating a missing CI check as a pass.
