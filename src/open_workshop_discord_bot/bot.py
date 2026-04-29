from __future__ import annotations

import logging

import aiohttp
import discord
from discord.ext import commands

from .config import ActivityConfig, BotConfig
from .health import HealthProbeServer
from .cogs.workshop import WorkshopCog
from .service import OpenWorkshopAPI
from .storage import StatisticsStorage


LOGGER = logging.getLogger(__name__)


class WorkshopBot(commands.Bot):
    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.http_session: aiohttp.ClientSession | None = None
        self.api: OpenWorkshopAPI | None = None
        self.statistics_storage = StatisticsStorage(self.config.storage.database_path)
        self.health_probe = HealthProbeServer(
            host=self.config.health.host,
            port=self.config.health.port,
        )

        self._presence_activity = _build_activity(self.config.discord.activity)
        self._presence_status = _parse_status(self.config.discord.status)
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents.default(),
            activity=self._presence_activity,
            status=self._presence_status,
        )

    async def setup_hook(self) -> None:
        await self.health_probe.start()
        try:
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
        except Exception:
            self.health_probe.mark_not_ready()
            await self._close_runtime_resources()
            await self.health_probe.stop()
            raise

    async def on_ready(self) -> None:
        self.health_probe.mark_ready()
        user_id = self.user.id if self.user is not None else "unknown"
        guilds = sorted(self.guilds, key=lambda guild: guild.name.lower())
        guild_summary = ", ".join(f"{guild.name}({guild.id})" for guild in guilds[:10])
        if len(guilds) > 10:
            guild_summary = f"{guild_summary}, ... +{len(guilds) - 10} more"
        LOGGER.info(
            "Logged in as %s (id=%s). Guilds=%d [%s]. Desired presence: status=%s, activity=%s:%r.",
            self.user,
            user_id,
            len(guilds),
            guild_summary or "none",
            self.config.discord.status,
            self.config.discord.activity.type,
            self.config.discord.activity.name,
        )
        if not guilds:
            LOGGER.warning(
                "The bot user is not a member of any guilds. "
                "Invite the application with the OAuth2 'bot' scope, not only 'applications.commands'."
            )
        if self.config.discord.status.strip().lower() in {"invisible", "offline"}:
            LOGGER.warning(
                "Configured Discord presence status %r is shown as offline by Discord.",
                self.config.discord.status,
            )

    async def _close_runtime_resources(self) -> None:
        if self.http_session is not None and not self.http_session.closed:
            await self.http_session.close()
        self.http_session = None
        self.api = None

    async def close(self) -> None:
        self.health_probe.mark_not_ready()
        await self.health_probe.stop()
        await self._close_runtime_resources()
        await super().close()

    @property
    def api_client(self) -> OpenWorkshopAPI:
        if self.api is None:
            raise RuntimeError("Open Workshop API client is not initialized.")
        return self.api


def _build_activity(activity_config: ActivityConfig) -> discord.BaseActivity:
    if activity_config.type.strip().lower() == "playing":
        return discord.Game(name=activity_config.name)
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
