# Torrento Telegram Bot

Linux Telegram bot that collects a magnet link, download name, and file type, then adds the torrent to Deluge with the correct destination folder.

## Flow

1. Send `/start`
2. Send a magnet link
3. Send the download name (used as the folder name)
4. Choose **Movie**, **TV show**, or **Other**

Downloads are saved under:

| Type    | Path |
|---------|------|
| Movie   | `/home/sharing/media/movies/<name>` |
| TV show | `/home/sharing/media/shows/<name>` |
| Other   | `/home/sharing/<name>` |

## Requirements

- Python 3.10+
- Deluge daemon with RPC enabled (`deluged`)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Setup 

```bash
cd /home/jbmild/project/torrento
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
chmod +x torrento-bot.py
```

Create your environment file:

```bash
sudo cp torrento-bot.env.example /etc/torrento-bot.env
sudo chmod 600 /etc/torrento-bot.env
sudo nano /etc/torrento-bot.env
```

Ensure Deluge RPC is configured in `~/.config/deluge/auth` or `/var/lib/deluge/.config/deluge/auth` and that the bot user can write to the sharing directories.

Run manually:

```bash
set -a && source /etc/torrento-bot.env && set +a
./torrento-bot.py
```

## systemd service

Adjust `User`, `Group`, `WorkingDirectory`, and `ExecStart` in `torrento-bot.service` if needed, then:

```bash
sudo cp torrento-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now torrento-bot
sudo systemctl status torrento-bot
```

## Commands

- `/start` — begin a new download request
- `/cancel` — cancel the current request
