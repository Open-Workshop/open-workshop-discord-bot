from __future__ import annotations

import asyncio
from contextlib import suppress
import logging

import aiohttp
import discord
from discord.ext import commands

from .config import ActivityConfig, BotConfig
from .cogs.workshop import WorkshopCog
from .service import OpenWorkshopAPI
from .storage import StatisticsStorage


LOGGER = logging.getLogger(__name__)
PRESENCE_REFRESH_DELAY_SECONDS = 10


class WorkshopBot(commands.Bot):
    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.http_session: aiohttp.ClientSession | None = None
        self.api: OpenWorkshopAPI | None = None
        self.statistics_storage = StatisticsStorage(self.config.storage.database_path)

        self._presence_activity = _build_activity(self.config.discord.activity)
        self._presence_status = _parse_status(self.config.discord.status)
        self._presence_refresh_task: asyncio.Task[None] | None = None
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.default(),
            activity=self._presence_activity,
            status=self._presence_status,
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
        LOGGER.info(
            "Logged in as %s. Desired presence: status=%s, activity=%s:%r.",
            self.user,
            self.config.discord.status,
            self.config.discord.activity.type,
            self.config.discord.activity.name,
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
            await self.change_presence(
                activity=self._presence_activity,
                status=self._presence_status,
            )
            LOGGER.info(
                "Presence refresh was sent after %d seconds.",
                PRESENCE_REFRESH_DELAY_SECONDS,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Presence refresh failed.")

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


def _build_activity(activity_config: ActivityConfig) -> discord.Activity:
    return discord.Activity(
        type=_parse_activity_type(activity_config.type),
        name=activity_config.name,
    )


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
