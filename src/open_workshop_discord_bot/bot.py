from __future__ import annotations

import logging

import aiohttp
import discord
from discord.ext import commands

from .config import Settings
from .cogs.workshop import WorkshopCog
from .service import OpenWorkshopAPI


LOGGER = logging.getLogger(__name__)


class WorkshopBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.http_session: aiohttp.ClientSession | None = None
        self.api: OpenWorkshopAPI | None = None

        activity = discord.Activity(
            type=discord.ActivityType.playing,
            name="скачивание модов",
        )
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.default(),
            activity=activity,
        )

    async def setup_hook(self) -> None:
        self.http_session = aiohttp.ClientSession()
        self.api = OpenWorkshopAPI(
            self.http_session,
            self.settings.api_url,
            request_timeout_seconds=self.settings.request_timeout_seconds,
            statistics_timeout_seconds=self.settings.statistics_timeout_seconds,
        )

        await self.add_cog(WorkshopCog(self))
        synced_commands = await self.tree.sync()
        LOGGER.info("Synced %d application commands.", len(synced_commands))

    async def close(self) -> None:
        if self.http_session is not None and not self.http_session.closed:
            await self.http_session.close()
        await super().close()

    @property
    def api_client(self) -> OpenWorkshopAPI:
        if self.api is None:
            raise RuntimeError("Open Workshop API client is not initialized.")
        return self.api
