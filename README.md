# Jonatron Telegram Bot

Linux Telegram bot that collects a magnet link, download name, and file type, then adds the torrent to Deluge with the correct destination folder.

Only the Telegram user `@joni_m91` can add torrents. Everyone else receives a welcome message.

## Architecture

The main menu routes each option to a **strategy** class in `strategies/`. To add a new menu action:

1. Create `strategies/your_action.py` implementing `BotStrategy`
2. Register it in `strategies/__init__.py` inside `STRATEGIES`

Each strategy owns its conversation states and handlers.

## Flow

1. Send `/start`
2. Choose **Add torrent** or **Restart server**
3. For torrents: send a magnet link, download name, then choose **Movie**, **TV show**, or **Other**
4. For restart: confirm **Yes, restart** (see [Restart server setup](#restart-server-setup) below)

### Restart server setup

The bot runs as a systemd service with no terminal, so `sudo reboot` cannot prompt for a password. Allow passwordless reboot for the service user:

```bash
# Find the reboot binary path on your system
which reboot

# Create a sudoers drop-in (use the path from `which reboot`)
sudo visudo -f /etc/sudoers.d/torrento-bot-reboot
```

Add this line (replace `jonatan` and the path if needed):

```
jonatan ALL=(root) NOPASSWD: /usr/sbin/reboot
```

Validate and test without rebooting:

```bash
sudo visudo -c
sudo -u jonatan sudo -l | grep reboot
```

You should see `NOPASSWD: /usr/sbin/reboot`. Then try **Restart server** in Telegram again.

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

Create the env file **in the project directory** (systemd reads this same file):

```bash
cd /home/jonatan/projects/jonatron
cp torrento-bot.env.example torrento-bot.env
chmod 600 torrento-bot.env
nano torrento-bot.env
```

Do not commit `torrento-bot.env`; it contains secrets.

Set these variables:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `DELUGE_HOST` | Deluge RPC host (default: `127.0.0.1`) |
| `DELUGE_PORT` | Deluge RPC port (default: `58846`) |
| `DELUGE_USERNAME` | Deluge RPC username (default: `localclient`) |
| `DELUGE_PASSWORD` | Deluge RPC password from the auth file |
| `DELUGE_TIMEOUT` | RPC connect timeout in seconds (default: `60`) |
| `DOWNLOAD_PATH_MOVIES` | Base folder for movie downloads + `<name>` |
| `DOWNLOAD_PATH_SHOWS` | Base folder for TV show downloads + `<name>` |
| `DOWNLOAD_PATH_OTHER` | Base folder for other downloads + `<name>` |

Each torrent is saved to `<base>/<name>/`, where `<name>` is what you enter in Telegram.

These paths must already exist and be **writable by the user running `deluged`** (on jarvis that is usually `debian-deluged`, not `jonatan`). Check Deluge's default in:

```bash
grep download_location /var/lib/deluged/config/core.conf
```

Set the `DOWNLOAD_PATH_*` values to match folders that user can write to.

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

Review the service file and adjust `User`, `Group`, `WorkingDirectory`, `EnvironmentFile`, and `ExecStart` if your paths differ.

The service loads env from the project directory, for example:

```ini
EnvironmentFile=/home/jonatan/projects/jonatron/torrento-bot.env
```

To point systemd at your project env file on jarvis:

```bash
sudo nano /etc/systemd/system/torrento-bot.service
```

Change the `EnvironmentFile=` line to your project path (adjust username/path if needed):

```ini
EnvironmentFile=/home/jonatan/projects/jonatron/torrento-bot.env
```

Then reload:

```bash
sudo systemctl daemon-reload
sudo systemctl restart torrento-bot
sudo journalctl -u torrento-bot -n 10 --no-pager
```

You should see `Deluge config from environment: host=127.0.0.1 port=58846`.

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
EnvironmentFile=/home/jonatan/projects/jonatron/torrento-bot.env
ExecStart=/home/jonatan/projects/jonatron/.venv/bin/python /home/jonatan/projects/jonatron/torrento-bot.py
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart torrento-bot
sudo journalctl -u torrento-bot -n 30 --no-pager
```

Ensure `torrento-bot.env` exists in the project directory and is readable by the service user:

```bash
chmod 600 ~/projects/jonatron/torrento-bot.env
grep DELUGE ~/projects/jonatron/torrento-bot.env
```

#### SSL handshake timeout

If you see `The handshake operation timed out`, the bot usually cannot reach `deluged` RPC.

Your earlier check showed Deluge RPC only on localhost:

```
127.0.0.1:58846
```

So `torrento-bot.env` **must** use:

```
DELUGE_HOST=127.0.0.1
DELUGE_PORT=58846
```

Not your server's public IP and not port `8112` (web UI).

Verify as the same user systemd uses:

```bash
sudo -u jonatan bash -lc '
  set -a && source /home/jonatan/projects/jonatron/torrento-bot.env && set +a
  echo "DELUGE_HOST=$DELUGE_HOST DELUGE_PORT=$DELUGE_PORT"
  /home/jonatan/projects/jonatron/.venv/bin/python - <<'"'"'EOF'"'"'
import os
from deluge_client import DelugeRPCClient
client = DelugeRPCClient(
    os.environ.get("DELUGE_HOST", "127.0.0.1"),
    int(os.environ.get("DELUGE_PORT", "58846")),
    os.environ.get("DELUGE_USERNAME", "localclient"),
    os.environ["DELUGE_PASSWORD"],
    timeout=60,
)
client.connect()
print("Connected to Deluge OK")
client.disconnect()
EOF
'
```

After fixing the env file:

```bash
sudo systemctl restart torrento-bot
sudo journalctl -u torrento-bot -n 20 --no-pager
```

## Commands

- `/start` — open the main menu (authorized users only)
- `/cancel` — cancel the current action (authorized users only)
