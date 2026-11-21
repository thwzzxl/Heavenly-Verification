# Heavenly Verification

A Discord bot I built for my Heavenly community using Python and discord.py.

It handles a two-step member verification process and provides basic security alerts.

## Features

- Rules acceptance and verification with persistent Discord buttons
- Automatic role assignment after verification
- A `!painel` command for administrators to post verification panels
- Verification logs and alerts for recently created accounts
- Alerts when multiple members join within a short period (no automatic punishment)
- Button cooldowns to prevent repeated clicks

## Tech

Python, discord.py, python-dotenv.

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in your own Discord bot token and channel/role IDs.
3. Enable **Server Members Intent** and **Message Content Intent** in the Discord Developer Portal.
4. Make sure the bot has the required channel and role permissions, and its role is above the roles it assigns.
5. Run `python verificacao.py`.
6. In the rules and verification channels, use `!painel` as an administrator to post the panels.

Do not commit your `.env` file or bot token. This repository contains example configuration only.
