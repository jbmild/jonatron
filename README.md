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

### 3. Install and configure Deluge

The bot talks to the **Deluge daemon** (`deluged`) over **RPC**, not through the web UI.

| Service | Default port | What it is |
|---------|--------------|------------|
| `deluge-web` | **8112** | Browser UI — the password you type at `server_ip:8112` |
| `deluged` | **58846** | RPC daemon — what the bot connects to |

These use **different passwords**. The web UI login does **not** go in `DELUGE_PASSWORD`.

Your bot env should use:

```
DELUGE_HOST=127.0.0.1
DELUGE_PORT=58846
DELUGE_USERNAME=localclient
DELUGE_PASSWORD=<from the auth file, not the web UI password>
```

Use `127.0.0.1` when the bot and Deluge run on the same server.

**Deluge 2.x** (including `2.1.2`) is supported by `deluge-client`. RPC still uses port `58846`. In Deluge 2, the auth file often has three parts — use only the first two in your env:

```
localclient:your_rpc_password:10
         ↑ username    ↑ DELUGE_PASSWORD   ↑ level (ignore)
```

You may see harmless version-probe warnings in Deluge logs when the bot connects; that is normal.

#### Find the RPC password

There is no single fixed path. Deluge creates `auth` inside **whoever runs `deluged`'s config directory**. If one path does not exist, use the steps below.

**Option A — Web UI (easiest if you already log in on port 8112)**

1. Open `http://your-server:8112`
2. Go to **Preferences** (gear icon) → **Connection Manager**
3. Select **Local Host** (or **127.0.0.1:58846**)
4. Click **Edit** — the **Username** and **Password** shown there are your RPC credentials

Put those in `torrento-bot.env`:

```
DELUGE_USERNAME=<username from Connection Manager>
DELUGE_PASSWORD=<password from Connection Manager>
```

**Option B — Find the auth file on disk**

Run on the server:

```bash
# Who runs Deluge?
ps aux | grep -E 'deluged|deluge-web'

# Is RPC listening?
ss -tlnp | grep 58846

# Search everywhere (may take a minute)
sudo find / -name auth -path '*/deluge/*' 2>/dev/null
```

If Deluge runs in **Docker**, the config is usually inside the container or a mounted volume:

```bash
docker ps
docker exec -it <container_name> find / -name auth -path '*/deluge/*' 2>/dev/null
# common mounts: /config/auth  or  /config/deluge/auth
```

Once you find the file:

```bash
sudo cat /path/to/deluge/auth
```

Example line:

```
localclient:a1b2c3d4e5f6...:10
```

Use the first two parts only in your env file.

**Option C — Derive config dir from the running process**

If `ps` shows something like `deluged -c /some/path`, the auth file is:

```
/some/path/auth
```

Some installs use:

| Setup | Typical auth path |
|-------|-------------------|
| your user | `~/.config/deluge/auth` |
| `sharing` user | `/home/sharing/.config/deluge/auth` |
| Debian `deluged` package | `/var/lib/deluge-daemon/auth` |
| `deluge` system user (old path) | `/var/lib/deluge/.config/deluge/auth` |
| Docker (linuxserver etc.) | `/config/auth` inside the container |

On **Debian/Ubuntu**, `deluged` often runs as `debian-deluged` with an explicit config dir. `ps` truncates long lines, so read the full path from `/proc`:

```bash
# Full command line (replace PID with deluged PID from ps)
tr '\0' ' ' < /proc/$(pgrep -f '/usr/bin/deluged')/cmdline; echo

# List likely config dirs
sudo ls /var/lib/ | grep -i delu
```

Example output: `deluged -d -c /var/lib/deluge-daemon` → auth is at `/var/lib/deluge-daemon/auth`.

When `-c /some/path` is set, the auth file is **`/some/path/auth`**, not `/some/path/.config/deluge/auth`.

#### If Deluge is not installed yet

The Python package `deluge-client` in this repo is **not** Deluge itself. Install the daemon:

```bash
sudo apt update
sudo apt install deluged deluge-web
```

Start Deluge as the same user that runs the bot (`sharing`):

```bash
sudo mkdir -p /home/sharing/.config/deluge
sudo chown -R sharing:sharing /home/sharing
sudo -u sharing deluged -d
sudo cat /home/sharing/.config/deluge/auth
```

#### Optional: set your own RPC password

Only do this after you know where Deluge's config directory is (from the steps above):

```bash
sudo systemctl stop deluged 2>/dev/null || sudo pkill deluged
echo 'localclient:your_chosen_password:10' | sudo tee /path/to/deluge/auth
sudo systemctl start deluged
```

Use the same password in `DELUGE_PASSWORD`.

#### Verify Deluge RPC is listening

```bash
ss -tlnp | grep 58846
```

You should see `deluged` on port `58846`. Port `8112` alone only means the web UI is up.

#### Test the connection

```bash
cd /home/jbmild/project/jonatron
set -a && source torrento-bot.env && set +a
.venv/bin/python - <<'EOF'
import os
from deluge_client import DelugeRPCClient

client = DelugeRPCClient(
    os.environ.get("DELUGE_HOST", "127.0.0.1"),
    int(os.environ.get("DELUGE_PORT", "58846")),
    os.environ.get("DELUGE_USERNAME", "localclient"),
    os.environ["DELUGE_PASSWORD"],
)
client.connect()
print("Connected to Deluge OK")
client.disconnect()
EOF
```

The bot user must be able to write to `/home/sharing` and its subdirectories.

### 4. Run manually (optional test)

For a quick local test, use an env file in the project directory instead of `/etc/torrento-bot.env`:

```bash
cd /home/jbmild/project/jonatron
cp torrento-bot.env.example torrento-bot.env
nano torrento-bot.env
set -a && source torrento-bot.env && set +a
.venv/bin/python torrento-bot.py
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
sudo journalctl -u torrento-bot -f    # follow logs live
sudo journalctl -u torrento-bot -n 50 --no-pager   # last 50 lines
```

#### Troubleshooting systemd

| `systemctl status` | Meaning |
|--------------------|---------|
| `status=217/USER` | The `User=` in the service file does not exist on this server |
| `status=200/CHDIR` | `WorkingDirectory=` path does not exist |
| `status=203/EXEC` | `ExecStart=` path wrong (missing `.venv` or script) |
| `status=1/FAILURE` | Bot crashed — check `journalctl` for Python errors |

The default service file uses `User=sharing` and `/home/jbmild/project/jonatron`. Edit it for your server before installing, for example on `jarvis` as user `jonatan`:

```bash
sudo nano /etc/systemd/system/torrento-bot.service
```

```ini
[Service]
User=jonatan
Group=jonatan
WorkingDirectory=/home/jonatan/projects/jonatron
EnvironmentFile=/etc/torrento-bot.env
ExecStart=/home/jonatan/projects/jonatron/.venv/bin/python /home/jonatan/projects/jonatron/torrento-bot.py
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart torrento-bot
sudo journalctl -u torrento-bot -n 30 --no-pager
```

Ensure `/etc/torrento-bot.env` exists and is readable by the service user:

```bash
sudo chown jonatan:jonatan /etc/torrento-bot.env
sudo chmod 600 /etc/torrento-bot.env
```

## Commands

- `/start` — begin a new download request (authorized users only)
- `/cancel` — cancel the current request (authorized users only)
