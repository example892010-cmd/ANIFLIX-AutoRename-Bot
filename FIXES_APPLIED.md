# ANIFLIX Auto-Rename Bot — publishing fixes

This package is based on the uploaded repository and keeps the existing settings, commands, and project layout.

## Changes

- The `published`-batch early return now checks the same ongoing destinations used by publishing, including globally configured fallback channels. A newly configured global ongoing channel will no longer be silently skipped just because the individual-channel target was already recorded.
- Manual-batch status lookup now normalizes season/episode values (for example, `S01` / episode `04`) and prefers the exact episode batch or selected route instead of a loosely matched stale row.
- The final status checks whether Telegram can still fetch the message IDs recorded for each channel before claiming a post is confirmed.
- Rename/storage failures are now returned to the manual-batch processor instead of being swallowed as a successful attempt. Unfinished source files remain resumable by sending the same `/batchN` command again.
- Publisher errors saved in MongoDB are included in the final batch summary.
- `/listanimechannels` now shows multiple ongoing targets and indicates when global fallback is used.
- Added unit tests for anime-specific and global ongoing-channel resolution.

## Verification

- `python -m compileall -q .` — passed.
- `python -m unittest discover -s tests -v` — 15 tests passed.

A live Telegram/Render integration test was not possible in this environment. After deployment, verify that the bot is an administrator with posting rights in both channels and that each ongoing anime has the required saved button/invite links configured.
