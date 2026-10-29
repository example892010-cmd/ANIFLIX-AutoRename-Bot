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

## `/batch1renamed` link-only publishing

- `/batch1renamed` still supports the normal already-renamed-file workflow when no URL is included.
- When a valid `http://` or `https://` URL is the line immediately after the episode number, the command switches to link-only publishing. It skips media download, renaming, File Store upload, and file storage.
- Link-only publishing resolves the anime's saved Anime Post channel, uses the shared Anime Post text template, and attaches the supplied URL to inline button(s).
- The link-only button template is configurable from Admin Panel → Anime Buttons → Link-only Batch Button.
- Supported label placeholders: `{title}`, `{anime}`, `{season}`, `{episode}`, `{episode_range}`. Use `#b`, `#r`, or `#g` to select button style. The URL field must be `{link}`, `{url}`, or `{stored_link}` so the command-supplied URL is used.
- Default: `#g EPISODE {episode} - {link}`.
