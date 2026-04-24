from __future__ import annotations

import asyncio
from io import BytesIO
import logging
import time
from typing import TYPE_CHECKING, cast

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from ..config import BotConfig
from ..service import OpenWorkshopError
from ..utils import (
    explain_invalid_workshop_link,
    format_count,
    format_duration,
    parse_discord_color,
    parse_workshop_id,
)

if TYPE_CHECKING:
    from ..bot import WorkshopBot


LOGGER = logging.getLogger(__name__)


class WorkshopCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._registered_commands: list[app_commands.Command] = []
        self._download_context_menu: app_commands.ContextMenu | None = None

    async def cog_load(self) -> None:
        self._registered_commands = [
            app_commands.Command(
                name=self.config.commands.statistics.name,
                description=self.config.commands.statistics.description,
                callback=self.statistics,
            ),
            app_commands.Command(
                name=self.config.commands.project.name,
                description=self.config.commands.project.description,
                callback=self.project,
            ),
            app_commands.Command(
                name=self.config.commands.download.name,
                description=self.config.commands.download.description,
                callback=self.download,
            ),
        ]

        for command in self._registered_commands:
            self.bot.tree.add_command(command)

        self._download_context_menu = app_commands.ContextMenu(
            name=self.config.commands.context_menu_name,
            callback=self.download_from_message_context,
        )
        self.bot.tree.add_command(self._download_context_menu)

    def cog_unload(self) -> None:
        for command in self._registered_commands:
            self.bot.tree.remove_command(command.name, type=command.type)
        self._registered_commands.clear()

        if self._download_context_menu is not None:
            self.bot.tree.remove_command(
                self._download_context_menu.name,
                type=self._download_context_menu.type,
            )
            self._download_context_menu = None

    @property
    def _typed_bot(self) -> "WorkshopBot":
        return cast("WorkshopBot", self.bot)

    @property
    def config(self) -> BotConfig:
        return self._typed_bot.config

    @property
    def api(self):
        return self._typed_bot.api_client

    @property
    def messages(self):
        return self.config.messages

    @property
    def ui(self):
        return self.config.ui

    @property
    def api_config(self):
        return self.config.api

    async def statistics(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        try:
            info = await self.api.fetch_statistics()
        except asyncio.TimeoutError:
            await interaction.followup.send(self.messages.statistics_timeout)
            return
        except (aiohttp.ClientError, OpenWorkshopError):
            await interaction.followup.send(self.messages.server_unavailable)
            return

        embed = discord.Embed(
            title=self.ui.statistics_embed_title,
            description=(
                f"Пользователям отправлено `{info.get('mods_sent_count', 0)}` файлов.\n"
                f"Сервис работает `{format_count(info.get('statistics_days', 0), ('день', 'дня', 'дней'))}`.\n\n"
                f"В каталоге `{format_count(info.get('games', 0), ('игра', 'игры', 'игр'))}` "
                f"и `{format_count(info.get('mods', 0), ('мод', 'мода', 'модов'))}`.\n"
                f"`{info.get('mods_dependencies', 0)}` из них имеют зависимости.\n"
                f"Сервису известно о `{info.get('genres', 0)}` жанрах игр "
                f"и `{info.get('mods_tags', 0)}` тегах для модов.\n\n"
                f"Бот находится на `{format_count(len(self.bot.guilds), ('сервере', 'серверах', 'серверах'))}`."
            ),
            color=parse_discord_color(self.ui.statistics_embed_color),
        )

        await interaction.followup.send(embed=embed)

    async def project(self, interaction: discord.Interaction) -> None:
        view = discord.ui.View()
        for button in self.ui.project_buttons:
            view.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    emoji=button.emoji,
                    label=button.label,
                    url=button.url,
                )
            )

        embed = discord.Embed(
            title=self.ui.project_embed_title,
            color=parse_discord_color(self.ui.project_embed_color),
        )
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.describe(link="Ссылка на мод или его ID")
    async def download(self, interaction: discord.Interaction, link: str) -> None:
        await self._handle_download(interaction, link)

    async def download_from_message_context(
        self,
        interaction: discord.Interaction,
        message: discord.Message,
    ) -> None:
        await self._handle_download(interaction, message.content)

    async def _handle_download(self, interaction: discord.Interaction, raw_link: str) -> None:
        started_at = time.perf_counter()
        await interaction.response.defer(thinking=True)

        mod_id_text = parse_workshop_id(raw_link)
        if mod_id_text is None:
            await interaction.followup.send(
                explain_invalid_workshop_link(raw_link, self.messages)
            )
            return

        mod_id = int(mod_id_text)
        if mod_id <= 0:
            await interaction.followup.send(self.messages.negative_mod_id)
            return

        try:
            mod_info = await self.api.fetch_mod_info(mod_id)
        except asyncio.TimeoutError:
            await interaction.followup.send(self.messages.server_unavailable)
            return
        except (aiohttp.ClientError, OpenWorkshopError):
            await interaction.followup.send(self.messages.server_unavailable)
            return

        result = mod_info.get("result")
        if isinstance(result, dict):
            try:
                size_bytes = int(result.get("size", 0) or 0)
            except (TypeError, ValueError):
                size_bytes = 0

            if size_bytes > self.api_config.direct_download_threshold_bytes:
                title_fallback = f"Ого! `{result.get('name', mod_id)}` весит {round(size_bytes / 1024 / 1024, 1)} мегабайт!"
                await interaction.followup.send(
                    embed=discord.Embed(
                        title=_safe_format(
                            self.messages.large_mod_title_template,
                            title_fallback,
                            name=result.get("name", mod_id),
                            size_mb=round(size_bytes / 1024 / 1024, 1),
                        ),
                        description=self.messages.large_mod_description,
                        color=parse_discord_color(self.ui.large_mod_embed_color),
                    ),
                    view=self._build_mod_links_view(mod_id, include_direct_download=True),
                )
                return

        try:
            download = await self.api.fetch_download(mod_id)
        except asyncio.TimeoutError:
            await interaction.followup.send(self.messages.server_unavailable)
            return
        except (aiohttp.ClientError, OpenWorkshopError):
            await interaction.followup.send(self.messages.server_unavailable)
            return

        if download.kind == "zip" and download.data:
            await interaction.edit_original_response(content=self.messages.download_started)
            elapsed = format_duration(time.perf_counter() - started_at)
            duration_fallback = f"Ваш запрос занял `{elapsed}`"
            await interaction.followup.send(
                content=_safe_format(
                    self.messages.download_duration_template,
                    duration_fallback,
                    elapsed=elapsed,
                ),
                file=discord.File(
                    BytesIO(download.data),
                    filename=download.filename or f"mod-{mod_id}.zip",
                ),
                view=self._build_mod_links_view(mod_id, include_direct_download=False),
            )
            return

        if download.kind == "json" and isinstance(download.json_data, dict):
            if download.json_data.get("error_id") in {0, 2, 3}:
                await interaction.followup.send(self.messages.mod_not_found)
            else:
                await interaction.followup.send(self.messages.unexpected_response)
            return

        LOGGER.warning(
            "Unexpected download response for mod %s with content type %s",
            mod_id,
            download.content_type,
        )
        await interaction.followup.send(self.messages.unexpected_response)

    def _build_mod_links_view(self, mod_id: int, *, include_direct_download: bool) -> discord.ui.View:
        view = discord.ui.View()

        if include_direct_download:
            view.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    label=self.ui.direct_download_button_label,
                    url=f"{self.api_config.base_url}/download/{mod_id}",
                )
            )

        view.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label=self.ui.website_button_label,
                url=f"{self.api_config.website_url}/mod/{mod_id}",
            )
        )
        return view


def _safe_format(template: str, fallback: str, **values: object) -> str:
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError):
        LOGGER.warning("Invalid message template in config, falling back to default text.")
        return fallback
