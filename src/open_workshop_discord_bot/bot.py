from __future__ import annotations

import logging

import aiohttp
import discord
from discord.ext import commands

from .config import ActivityConfig, BotConfig
from .cogs.workshop import WorkshopCog
from .service import OpenWorkshopAPI


LOGGER = logging.getLogger(__name__)


class WorkshopBot(commands.Bot):
    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.http_session: aiohttp.ClientSession | None = None
        self.api: OpenWorkshopAPI | None = None

        activity = _build_activity(self.config.discord.activity)
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.default(),
            activity=activity,
            status=_parse_status(self.config.discord.status),
        )

    async def setup_hook(self) -> None:
        self.http_session = aiohttp.ClientSession()
        self.api = OpenWorkshopAPI(
            self.http_session,
            self.config.api.base_url,
            request_timeout_seconds=self.config.api.request_timeout_seconds,
            statistics_timeout_seconds=self.config.api.statistics_timeout_seconds,
        )

        await self.add_cog(WorkshopCog(self))
        if self.config.discord.sync_commands_on_startup:
            synced_commands = await self.tree.sync()
            LOGGER.info("Synced %d application commands.", len(synced_commands))
        else:
            LOGGER.info("Skipped application command sync because it is disabled in config.")

    async def close(self) -> None:
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
