from __future__ import annotations

import asyncio
from contextlib import suppress
import json
import logging
import time
from typing import Any

import aiohttp
import discord
from discord.ext import commands

from .config import ActivityConfig, BotConfig
from .cogs.workshop import WorkshopCog
from .service import OpenWorkshopAPI
from .storage import StatisticsStorage


LOGGER = logging.getLogger(__name__)
PRESENCE_REFRESH_DELAY_SECONDS = 10
PRESENCE_ACTIVITY_DELAY_SECONDS = 5
PRESENCE_REFRESH_INTERVAL_SECONDS = 60


class WorkshopBot(commands.Bot):
    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.http_session: aiohttp.ClientSession | None = None
        self.api: OpenWorkshopAPI | None = None
        self.statistics_storage = StatisticsStorage(self.config.storage.database_path)

        self._presence_activity_payload = _build_activity_payload(self.config.discord.activity)
        self._presence_status = _parse_status(self.config.discord.status)
        self._presence_refresh_task: asyncio.Task[None] | None = None
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.default(),
        )

    async def setup_hook(self) -> None:
        self.http_session = aiohttp.ClientSession()
        await self.statistics_storage.initialize()
        self.api = OpenWorkshopAPI(
            self.http_session,
            self.config.api.base_url,
            request_timeout_seconds=self.config.api.request_timeout_seconds,
        )

        await self.add_cog(WorkshopCog(self))
        if self.config.discord.sync_commands_on_startup:
            synced_commands = await self.tree.sync()
            LOGGER.info("Synced %d application commands.", len(synced_commands))
        else:
            LOGGER.info("Skipped application command sync because it is disabled in config.")

    async def on_ready(self) -> None:
        user_id = self.user.id if self.user is not None else "unknown"
        guilds = sorted(self.guilds, key=lambda guild: guild.name.lower())
        guild_summary = ", ".join(f"{guild.name}({guild.id})" for guild in guilds[:10])
        if len(guilds) > 10:
            guild_summary = f"{guild_summary}, ... +{len(guilds) - 10} more"
        LOGGER.info(
            "Logged in as %s (id=%s). Guilds=%d [%s]. Desired presence: status=%s, activity_payload=%s.",
            self.user,
            user_id,
            len(guilds),
            guild_summary or "none",
            self.config.discord.status,
            self._presence_activity_payload,
        )
        if self.config.discord.status.strip().lower() in {"invisible", "offline"}:
            LOGGER.warning(
                "Configured Discord presence status %r is shown as offline by Discord.",
                self.config.discord.status,
            )
        if self._presence_refresh_task is None or self._presence_refresh_task.done():
            self._presence_refresh_task = asyncio.create_task(self._refresh_presence_after_ready())

    async def _refresh_presence_after_ready(self) -> None:
        try:
            await asyncio.sleep(PRESENCE_REFRESH_DELAY_SECONDS)
            while not self.is_closed():
                await self._send_gateway_presence(activity_payload=None)
                LOGGER.info(
                    "Gateway presence status payload was sent: status=%s.",
                    _gateway_status(self._presence_status),
                )

                await asyncio.sleep(PRESENCE_ACTIVITY_DELAY_SECONDS)
                await self._send_gateway_presence(activity_payload=self._presence_activity_payload)
                LOGGER.info(
                    "Gateway presence activity payload was sent: status=%s, activity_payload=%s.",
                    _gateway_status(self._presence_status),
                    self._presence_activity_payload,
                )

                await asyncio.sleep(PRESENCE_REFRESH_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Presence refresh failed.")

    async def _send_gateway_presence(self, *, activity_payload: dict[str, Any] | None) -> None:
        if self.ws is None:
            raise RuntimeError("Discord websocket is not initialized.")

        status = _gateway_status(self._presence_status)
        payload = {
            "op": 3,
            "d": {
                "since": int(time.time() * 1000) if status == "idle" else None,
                "activities": [] if activity_payload is None else [activity_payload],
                "status": status,
                "afk": False,
            },
        }
        LOGGER.info("Sending docs-compliant gateway presence payload: %s", payload)
        await self.ws.send(json.dumps(payload, ensure_ascii=False))

    async def close(self) -> None:
        if self._presence_refresh_task is not None and not self._presence_refresh_task.done():
            self._presence_refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._presence_refresh_task
        if self.http_session is not None and not self.http_session.closed:
            await self.http_session.close()
        await super().close()

    @property
    def api_client(self) -> OpenWorkshopAPI:
        if self.api is None:
            raise RuntimeError("Open Workshop API client is not initialized.")
        return self.api


def _build_activity_payload(activity_config: ActivityConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": activity_config.name,
        "type": _parse_activity_type(activity_config.type).value,
    }
    return payload


def _parse_activity_type(value: str) -> discord.ActivityType:
    normalized = value.strip().lower()
    mapping = {
        "playing": discord.ActivityType.playing,
        "streaming": discord.ActivityType.streaming,
        "listening": discord.ActivityType.listening,
        "watching": discord.ActivityType.watching,
        "competing": discord.ActivityType.competing,
    }
    try:
        return mapping[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported activity type: {value!r}") from exc


def _parse_status(value: str) -> discord.Status:
    normalized = value.strip().lower()
    mapping = {
        "online": discord.Status.online,
        "idle": discord.Status.idle,
        "dnd": discord.Status.dnd,
        "do_not_disturb": discord.Status.dnd,
        "invisible": discord.Status.invisible,
        "offline": discord.Status.offline,
    }
    try:
        return mapping[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported presence status: {value!r}") from exc


def _gateway_status(status: discord.Status) -> str:
    if status is discord.Status.offline:
        return "invisible"
    return str(status)
