from __future__ import annotations

import inspect
import logging
import os
import re
import time
from enum import Enum
from pathlib import Path

from deluge_client import DelugeRPCClient

logger = logging.getLogger(__name__)

BASE_OTHER = Path("/home/sharing")
BASE_MOVIES = Path("/home/sharing/media/movies")
BASE_SHOWS = Path("/home/sharing/media/shows")

MAGNET_PREFIX = re.compile(r"^magnet:\?", re.IGNORECASE)
INVALID_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class FileType(str, Enum):
    MOVIE = "movie"
    TV_SHOW = "tv_show"
    OTHER = "other"


def get_deluge_client() -> DelugeRPCClient:
    host = os.environ.get("DELUGE_HOST", "127.0.0.1").strip()
    if host in {"localhost", "::1"}:
        host = "127.0.0.1"
    port = int(os.environ.get("DELUGE_PORT", "58846"))
    username = os.environ.get("DELUGE_USERNAME", "localclient")
    password = os.environ.get("DELUGE_PASSWORD")
    timeout = int(os.environ.get("DELUGE_TIMEOUT", "60"))
    if not password:
        raise RuntimeError("DELUGE_PASSWORD is not set in the environment.")

    init_params = inspect.signature(DelugeRPCClient.__init__).parameters
    client_kwargs = {"timeout": timeout} if "timeout" in init_params else {}
    if "username" in init_params:
        return DelugeRPCClient(host, port, username, password, **client_kwargs)
    return DelugeRPCClient(host, port, password, **client_kwargs)


def connect_deluge(client: DelugeRPCClient) -> None:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            logger.info(
                "Connecting to Deluge at %s:%s (attempt %s)",
                client.host,
                client.port,
                attempt,
            )
            client.connect()
            return
        except Exception as exc:
            last_error = exc
            logger.warning("Deluge connection attempt %s failed: %s", attempt, exc)
            try:
                client.disconnect()
            except Exception:
                pass
            if attempt < 3:
                time.sleep(2)

    raise RuntimeError(
        f"Could not connect to Deluge at {client.host}:{client.port}. "
        "If Deluge listens on 127.0.0.1 only, set DELUGE_HOST=127.0.0.1 in your env file. "
        f"Last error: {last_error}"
    ) from last_error


def sanitize_name(name: str) -> str:
    cleaned = INVALID_NAME_CHARS.sub("_", name.strip())
    cleaned = cleaned.strip(". ")
    if not cleaned:
        raise ValueError("Download name cannot be empty.")
    return cleaned


def download_path_for(file_type: FileType, name: str) -> Path:
    safe_name = sanitize_name(name)
    if file_type is FileType.MOVIE:
        return BASE_MOVIES / safe_name
    if file_type is FileType.TV_SHOW:
        return BASE_SHOWS / safe_name
    return BASE_OTHER / safe_name


def add_magnet_to_deluge(magnet: str, download_path: Path) -> str:
    download_path.mkdir(parents=True, exist_ok=True)
    client = get_deluge_client()
    connect_deluge(client)
    try:
        torrent_id = client.call(
            "core.add_torrent_magnet",
            magnet.strip(),
            {"download_location": str(download_path), "add_paused": False},
        )
    finally:
        client.disconnect()

    if not torrent_id:
        raise RuntimeError("Deluge did not return a torrent id.")
    return torrent_id


def validate_deluge_config() -> DelugeRPCClient:
    deluge_port = os.environ.get("DELUGE_PORT", "58846")
    if deluge_port == "8112":
        raise RuntimeError(
            "DELUGE_PORT=8112 is the web UI port, not RPC. Use DELUGE_PORT=58846."
        )
    return get_deluge_client()
