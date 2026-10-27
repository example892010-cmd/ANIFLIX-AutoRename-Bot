# ANIFLIX Auto-Rename Bot

A Pyrogram-based Telegram file renamer with per-user filename templates, optional metadata editing, saved thumbnails, custom captions, an optional force-subscription gate, and admin tools.

## Features

- `/autorename` saves a personal filename template.
- Supported template placeholders: `{title}`, `{season}`, `{episode}`, `{quality}`.
- `/setmedia` selects Document, Video, or Audio output where the file type is compatible.
- `/set_caption`, `/see_caption`, `/del_caption` manage captions. Caption placeholders: `{filename}`, `{filesize}`, `{duration}`.
- Send a photo to save it as a thumbnail; `/viewthumb` and `/delthumb` manage it.
- `/metadata` toggles optional metadata; `/settitle`, `/setauthor`, `/setartist`, `/setaudio`, `/setsubtitle`, and `/setvideo` configure metadata values.
- Admin commands include `/stats`, `/broadcast`, and `/restart`.
- `/health` is available for Render health checks.

## Required environment variables

Set these in the Render service dashboard. Do not commit secret values to GitHub.

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | Yes | Token from BotFather |
| `API_ID` | Yes | Numeric Telegram API ID from my.telegram.org |
| `API_HASH` | Yes | Telegram API hash |
| `DB_URL` | Yes | MongoDB connection string (`mongodb://` or `mongodb+srv://`) |
| `ADMIN` | Recommended | Your Telegram numeric user ID; separate multiple IDs with spaces |
| `DB_NAME` | No | Defaults to `autorenamebot` |
| `LOG_CHANNEL` | No | Numeric channel ID for logs and `/bought` screenshots |
| `SUPPORT_CHAT` | No | Numeric support chat ID for startup notifications |
| `FORCE_SUB_CHANNELS` | No | Comma-separated public channel usernames, without `@`; empty disables this feature |
| `START_PIC` | No | URL for the `/start` image |
| `WEBHOOK` | No | Enables the small HTTP health server; defaults to `true` |

The bot uses MongoDB for user settings. Create a MongoDB database and allow your Render service to connect before starting the bot.

## Deploy on Render

1. Push the contents of this repository to your GitHub repository.
2. In Render, create a Blueprint from that repository, or create a Docker-based Web Service using the included `Dockerfile`.
3. Enter `BOT_TOKEN`, `API_ID`, `API_HASH`, and `DB_URL` in the environment settings. Set `ADMIN` to your Telegram numeric user ID so admin commands are available.
4. Deploy and check `/health` in the service logs or browser.
5. Open the Telegram bot, run `/start`, then save a template, for example:

   `/autorename @ANIFLIXANIMETAMIL - {title} S{season} Ep{episode} [{quality}] [TAMIL]`

## Notes

- Metadata editing requires FFmpeg. The included Dockerfile installs it.
- Files with no detected season or episode use `XX`; unknown quality uses `Unknown`.
- Render Free has an ephemeral filesystem, so downloaded files are temporary. Persistent settings are stored in MongoDB.
- Live Telegram operations still require valid credentials, an accessible MongoDB deployment, and successful network access; syntax/tests alone cannot validate those external services.

## License and upstream credit

This project preserves the upstream MIT license in `LICENSE`. See the license and original source attribution before redistributing modifications.
