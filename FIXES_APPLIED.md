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

## `/batch1renamed` link-only dual publishing

- `/batch1renamed` still supports the normal already-renamed-file workflow when no URL is included.
- When a valid `http://` or `https://` URL is included after the episode number, the command takes a link-only path. It does not download, rename, upload, or store media again.
- Anime Post and Ongoing publication are attempted independently. A failure in one destination does not stop the attempt to publish to the other.
- Anime Post uses the saved Anime Post text and the configurable Link-only Batch Button template; each configured link-only button points to the URL supplied in the command.
- Ongoing uses the anime's saved poster, the shared Main Ongoing Post Text, the saved Ongoing Buttons template, and the invite links saved for that anime. Its season and episode placeholders are overridden with the values entered in `/batch1renamed`.
- Ongoing destinations use the anime's assigned channels, falling back to active globally configured Ongoing Channels when no per-anime destinations are assigned.
- Anime Post sends use the Bot API directly for private numeric channel IDs. This avoids Pyrogram `PEER_ID_INVALID` failures caused by an empty local peer cache after a Render restart.
- The bot replies with separate Anime Post and Ongoing results, so partial publishing failures are visible.
- The link-only button template is configurable from Admin Panel → Anime Buttons → Link-only Batch Button. Supported label placeholders: `{title}`, `{anime}`, `{season}`, `{episode}`, `{episode_range}`. Use `#b`, `#r`, or `#g` for button style. The URL field must be `{link}`, `{url}`, or `{stored_link}`.

## Verification

- `python -m compileall -q .` — passed.
- `python -m unittest discover -s tests -v` — 34 tests passed.
- `python apply_fix.py --check` — passed; this command is now read-only and only verifies that the fix is present.
- Live Telegram posting was not tested here. After deployment, confirm the bot is an administrator with posting permission in the Anime Post and Ongoing channels, and that the anime has a saved invite link when the Ongoing Buttons template uses `{anime_invite}`.
