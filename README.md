# 🍥 ANIFLIX Auto-Rename Bot

A private Telegram bot for renaming video and document files.

## Features

- Rename files using a custom filename format.
- Configure a thumbnail.
- Save metadata text settings.
- Restrict access to the bot owner.
- Lightweight Python application.
- Render health-check endpoint.

## Required Environment Variables

Configure these in your Render dashboard:

- `BOT_TOKEN` — Telegram bot token from @BotFather.
- `OWNER_ID` — Your numeric Telegram user ID.

## Filename Format

Use `/format` to configure the filename template.

Available placeholders:

- `{title}` — Original filename without its extension.
- `{season}` — Season number, if supplied by the filename.
- `{episode}` — Episode number, if supplied by the filename.
- `{quality}` — Video quality, if supplied by the filename.
- `{extension}` — Original file extension without the dot.

Example:

`/format @ANIFLIXANIMETAMIL - {title} S{season} Ep{episode} [{quality}] [TAMIL]`

## Commands

- `/start` — Start the bot.
- `/help` — Show help.
- `/format` — Set filename format.
- `/setthumb` — Save a thumbnail by replying to a photo.
- `/viewthumb` — View the saved thumbnail.
- `/delthumb` — Clear the thumbnail setting.
- `/metadata` — View metadata settings.
- `/setmetadata` — Save metadata text.
- `/resetmetadata` — Clear metadata text.

## Deployment

1. Push the project files to GitHub.
2. Create a Web Service on Render.
3. Connect this repository.
4. Select the Free plan.
5. Set `BOT_TOKEN` and `OWNER_ID` as environment variables.
6. Deploy the service.

## Important Notes

- Render Free services may sleep or restart.
- Local files can be lost when the service restarts or redeploys.
- Large file transfers may fail because of Telegram, network, or hosting limits.
- Thumbnail and metadata settings are not fully applied to returned media in the initial version.
