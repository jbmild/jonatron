# Jonatron Telegram Bot

Linux Telegram bot that collects a magnet link, download name, and file type, then adds the torrent to Deluge with the correct destination folder.

Only the Telegram user `@joni_m91` can add torrents. Everyone else receives a welcome message.

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
- A Linux user that can write to the sharing directories (the service file uses `sharing`)

## Configuration

### 1. Install the bot

```bash
cd /home/jbmild/project/jonatron
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
chmod +x torrento-bot.py
```

### 2. Create the environment file

Copy the example file, edit it with your values, and give the bot user read access:

```bash
sudo cp torrento-bot.env.example /etc/torrento-bot.env
sudo chown sharing:sharing /etc/torrento-bot.env
sudo chmod 600 /etc/torrento-bot.env
sudo nano /etc/torrento-bot.env
```

The `chown` step is required. Without it, only root can read the file and the systemd service (which runs as `sharing`) will fail to start.

Set these variables:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `DELUGE_HOST` | Deluge RPC host (default: `127.0.0.1`) |
| `DELUGE_PORT` | Deluge RPC port (default: `58846`) |
| `DELUGE_USERNAME` | Deluge RPC username (default: `localclient`) |
| `DELUGE_PASSWORD` | Deluge RPC password from the auth file |

### 3. Configure Deluge RPC

Ensure Deluge RPC is enabled. The auth file uses `username:password` lines, for example:

```
localclient:your_deluge_rpc_password
```

Match `DELUGE_USERNAME` and `DELUGE_PASSWORD` to that entry in:

- `~/.config/deluge/auth`, or
- `/var/lib/deluge/.config/deluge/auth`

The bot user must be able to write to `/home/sharing` and its subdirectories.

### 4. Run manually (optional test)

For a quick local test, use an env file in the project directory instead of `/etc/torrento-bot.env`:

```bash
cd /home/jbmild/project/jonatron
cp torrento-bot.env.example torrento-bot.env
nano torrento-bot.env
set -a && source torrento-bot.env && set +a
./torrento-bot.py
```

Do not commit `torrento-bot.env`; it contains secrets.

Send `/start` to the bot from `@joni_m91` to verify the magnet flow works.

## Run on server startup

The included `torrento-bot.service` unit starts the bot automatically when the server boots.

Review the service file and adjust `User`, `Group`, `WorkingDirectory`, or `ExecStart` if your paths or service user differ.

Install and enable the service:

```bash
sudo cp torrento-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable torrento-bot
sudo systemctl start torrento-bot
sudo systemctl status torrento-bot
```

`enable` registers the service for startup on boot. `start` runs it immediately without rebooting.

Useful commands:

```bash
sudo systemctl restart torrento-bot   # apply config or code changes
sudo systemctl stop torrento-bot
sudo journalctl -u torrento-bot -f    # follow logs
```

## Commands

- `/start` — begin a new download request (authorized users only)
- `/cancel` — cancel the current request (authorized users only)
