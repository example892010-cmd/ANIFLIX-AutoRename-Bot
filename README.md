# ANIFLIX `/batch1renamed` dual-publish fix

This is a targeted patch package for `example892010-cmd/ANIFLIX-AutoRename-Bot`.
It changes only these two existing project files:

- `plugins/file_rename.py`
- `plugins/ongoing_posts.py`

## What it changes

When `/batch1renamed` is sent with an already-stored URL, the bot attempts both publishing destinations independently:

1. **Anime Post** uses the saved Anime Post caption template and the configured link-only episode button.
2. **Ongoing** uses the saved Main Ongoing Post Text, Ongoing Buttons, poster, invite links, and anime-specific ongoing destination(s).
3. The supplied season and episode are used in the Ongoing caption for this run. The saved Ongoing settings are not overwritten.
4. The reply reports Anime Post and Ongoing outcomes separately, including destination-specific errors.
5. The link-only command still does not download, rename, upload, or store media again.

The ordinary `/batch1` file workflow and the existing `/ongoing` command remain compatible.

## Apply

1. Extract this ZIP.
2. Copy `apply_fix.py` into the root of your existing bot repository (the folder that contains `plugins/`).
3. Run `python apply_fix.py --check`.
4. Run `python apply_fix.py`.
5. Run `python -m compileall -q plugins` and deploy the updated project.

The script creates `.bak` copies of the two original files before replacing them. It is safe to run again; it will not add duplicate imports or keep re-editing an already-patched source.

## Tests included

Run from the extracted ZIP folder:

```bash
python -m unittest discover -s tests -v
```

These tests validate the patch transformations, independent destination attempts, passed-through episode values, no-media link-only behavior, and idempotence. They are local patch tests; they do not contact Telegram or verify your live channel permissions, Bot API credentials, MongoDB data, or Render deployment.
