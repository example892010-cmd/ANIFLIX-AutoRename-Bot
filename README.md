# ANIFLIX Auto-Rename Bot

A Pyrogram-based Telegram file renamer with per-user filename templates, optional metadata editing, saved thumbnails, custom captions, an optional force-subscription gate, and admin tools.

## Features

- `/autorename` saves a personal filename template.
- Supported template placeholders: `{title}`, `{season}`, `{episode}`, `{quality}`.
- `/setmedia` selects Document, Video, or Audio output where the file type is compatible.
- `/set_caption`, `/see_caption`, `/del_caption` manage captions. Caption placeholders: `{filename}`, `{filesize}`, `{duration}`.
- Send a photo to save it as a thumbnail; `/viewthumb` and `/delthumb` manage it.
- `/metadata` toggles optional metadata; `/settitle`, `/setauthor`, `/setartist`, `/setaudio`, `/setsubtitle`, and `/setvideo` configure metadata values.
- Admin commands include `/admin`, `/stats`, `/broadcast`, and `/restart`.
- `/health` is available for Render health checks.
- Completed episode groups are stored in the dump channel, verified, and automatically published to the anime's individual channel with 480p / 720p / 1080p quality buttons.
- `/ongoing Anime Title` publishes the saved ongoing template and poster with the anime's saved invite-link buttons to its configured ongoing channels.
- `/admin` provides inline-button menus for Anime Channels, Anime Invite Links (add/edit/remove/view), Episode Manager, Link Verification, Post Customization, Anime Post, Ongoing Post, Ongoing Details, Ongoing Channels, Force Subscribe, and Bot Settings.
- Force Subscribe supports up to seven channels. In Admin Panel → Force Subscribe → Add Channel, add the bot as an administrator, forward an original post from that channel, send its invite URL, and choose normal join or join-request. File deep links check every configured channel before delivering media; unjoined users receive Join buttons and a Try Again button. Admin IDs bypass the gate, so test with a non-admin Telegram account.
- Non-admins can only use saved `file_...` deep links to retrieve files; rename commands and other bot features are admin-only.

## Required environment variables

Set these in the Render service dashboard. Do not commit secret values to GitHub.

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | Yes | Token from BotFather |
| `API_ID` | Yes | Numeric Telegram API ID from my.telegram.org |
| `API_HASH` | Yes | Telegram API hash |
| `DB_URL` | Yes | MongoDB connection string (`mongodb://` or `mongodb+srv://`) |
| `STORAGE_CHANNEL_ID` | Yes for file-store links | Numeric private dump-channel ID. The bot must be an administrator there. `DUMP_CHANNEL` is accepted as a compatibility fallback. |
| `ADMIN` | Recommended | Your Telegram numeric user ID; separate multiple IDs with spaces |
| `DB_NAME` | No | Defaults to `autorenamebot` |
| `LOG_CHANNEL` | No | Numeric channel ID for logs and `/bought` screenshots |
| `SUPPORT_CHAT` | No | Numeric support chat ID for startup notifications |
| `FORCE_SUB_CHANNELS` | No | Legacy comma-separated channel usernames used only when the Admin Panel has no saved Force Subscribe configuration. |
| `START_PIC` | No | URL for the `/start` image |
| `WEBHOOK` | No | Enables the small HTTP health server; defaults to `true` |

The bot uses MongoDB for user settings. Create a MongoDB database and allow your Render service to connect before starting the bot.

## Deploy on Render

1. Push the contents of this repository to your GitHub repository.
2. In Render, create a Blueprint from that repository, or create a Docker-based Web Service using the included `Dockerfile`.
3. Enter `BOT_TOKEN`, `API_ID`, `API_HASH`, and `DB_URL` in the environment settings. Set `ADMIN` to your Telegram numeric user ID so admin commands are available.
4. Deploy and check `/health` in the service logs or browser.
5. Open the Telegram bot as an admin and run `/start`, then `/admin` to configure channels, templates, invite links, and Force Subscribe.
6. Save the renaming template, for example:

   `/autorename @ANIFLIXANIMETAMIL - {title} S{season} Ep{episode} [{quality}] [TAMIL]`
7. Assign an individual Anime Post channel to each anime. Upload files in all three qualities. The post is published only after all three stored files are independently verified.
8. Add ongoing invite links and save the ongoing template/poster for each anime. Set the ongoing details, then publish with `/ongoing Anime Title`.

## Notes

- Metadata editing requires FFmpeg. The included Dockerfile installs it.
- Files with no detected season or episode use `XX`; unknown quality uses `Unknown`.
- Render Free has an ephemeral filesystem, so downloaded files are temporary. Persistent settings are stored in MongoDB.
- Add the bot as an administrator with posting permission in each Anime Post and Ongoing channel. Add it as an administrator in every Force Subscribe channel so membership checks can be made reliably.
- For a join-request channel, supply an invite link that Telegram has been configured to use for join requests. The bot will continue to deny file access until the request is approved and membership is visible.
- Live Telegram operations still require valid credentials, an accessible MongoDB deployment, and successful network access; syntax/tests alone cannot validate those external services.

## License and upstream credit

This project preserves the upstream MIT license in `LICENSE`. See the license and original source attribution before redistributing modifications.

## Ongoing post button templates

Open `/admin` → **Ongoing Buttons** to edit the shared button template used by ongoing-channel posts. Add one button per line using `#b Button Name - URL`, where `#b` is blue, `#r` is red, and `#g` is green. Use `{anime_invite}` for a saved invite URL; a button named **DOWNLOAD NOW** also automatically uses the current anime's saved invite link. The **Refresh Template** control reloads the currently saved template.

The file progress status also includes **Refresh Progress** for both download and upload stages. The rename handler skips video probing when a recognized quality is already in the filename and probes only when quality is unknown.
