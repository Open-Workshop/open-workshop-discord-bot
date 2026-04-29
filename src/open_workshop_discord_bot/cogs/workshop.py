from __future__ import annotations

import asyncio
from datetime import date
from io import BytesIO
import logging
import time
from typing import TYPE_CHECKING, cast

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from ..config import BotConfig
from ..service import OpenWorkshopError, OpenWorkshopNotFoundError
from ..storage import StatisticsSnapshot
from ..utils import (
    explain_invalid_workshop_link,
    format_count,
    format_duration,
    parse_discord_color,
    parse_workshop_reference,
    WorkshopReference,
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
    def statistics_storage(self):
        return self._typed_bot.statistics_storage

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
        info = await self.statistics_storage.fetch_statistics()

        embed = discord.Embed(
            title=self.ui.statistics_embed_title,
            description=_build_statistics_description(info, guild_count=len(self.bot.guilds)),
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

        reference = parse_workshop_reference(raw_link)
        if reference is None:
            await interaction.followup.send(
                explain_invalid_workshop_link(raw_link, self.messages)
            )
            return

        if reference.id <= 0:
            await interaction.followup.send(self.messages.negative_mod_id)
            return

        try:
            mod_id, mod_info = await self._fetch_mod_info(reference)
        except OpenWorkshopNotFoundError:
            await self._record_statistics_outcome("mod_not_found")
            await interaction.followup.send(self.messages.mod_not_found)
            return
        except asyncio.TimeoutError:
            await self._record_statistics_outcome("failed_request")
            await interaction.followup.send(self.messages.server_unavailable)
            return
        except (aiohttp.ClientError, OpenWorkshopError):
            await self._record_statistics_outcome("failed_request")
            await interaction.followup.send(self.messages.server_unavailable)
            return

        try:
            size_bytes = int(mod_info.get("size", 0) or 0)
        except (TypeError, ValueError):
            size_bytes = 0

        if size_bytes > self.api_config.direct_download_threshold_bytes:
            await self._record_statistics_outcome("direct_link_sent")
            title_fallback = f"Ого! `{mod_info.get('name', mod_id)}` весит {round(size_bytes / 1024 / 1024, 1)} мегабайт!"
            await interaction.followup.send(
                embed=discord.Embed(
                    title=_safe_format(
                        self.messages.large_mod_title_template,
                        title_fallback,
                        name=mod_info.get("name", mod_id),
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
        except OpenWorkshopNotFoundError:
            await self._record_statistics_outcome("mod_not_found")
            await interaction.followup.send(self.messages.mod_not_found)
            return
        except asyncio.TimeoutError:
            await self._record_statistics_outcome("failed_request")
            await interaction.followup.send(self.messages.server_unavailable)
            return
        except (aiohttp.ClientError, OpenWorkshopError):
            await self._record_statistics_outcome("failed_request")
            await interaction.followup.send(self.messages.server_unavailable)
            return

        if download.kind == "zip" and download.data:
            await self._record_statistics_outcome("file_sent")
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

        LOGGER.warning(
            "Unexpected download response for mod %s with content type %s",
            mod_id,
            download.content_type,
        )
        await self._record_statistics_outcome("failed_request")
        await interaction.followup.send(self.messages.unexpected_response)

    def _build_mod_links_view(self, mod_id: int, *, include_direct_download: bool) -> discord.ui.View:
        view = discord.ui.View()

        if include_direct_download:
            view.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    label=self.ui.direct_download_button_label,
                    url=f"{self.api_config.website_url}/mod/{mod_id}/download",
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

    async def _record_statistics_outcome(self, outcome: str) -> None:
        try:
            await self.statistics_storage.record_download_outcome(outcome)
        except Exception:
            LOGGER.exception("Failed to record statistics outcome %s", outcome)

    async def _fetch_mod_info(self, reference: WorkshopReference) -> tuple[int, dict]:
        if reference.kind == "steam":
            return await self.api.fetch_mod_info_by_source_id("steam", reference.id)

        try:
            return reference.id, await self.api.fetch_mod_info(reference.id)
        except OpenWorkshopNotFoundError:
            if reference.kind != "unknown":
                raise
            return await self.api.fetch_mod_info_by_source_id("steam", reference.id)


def _safe_format(template: str, fallback: str, **values: object) -> str:
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError):
        LOGGER.warning("Invalid message template in config, falling back to default text.")
        return fallback


def _build_statistics_description(info: StatisticsSnapshot, *, guild_count: int) -> str:
    lines = [
        f"За сегодня было `{format_count(info.today.requests_count, ('запрос', 'запроса', 'запросов'))}`.",
        (
            f"Из них отправлено `{info.today.files_sent_count}` файлов, "
            f"`{info.today.direct_links_count}` прямых ссылок, "
            f"`{info.today.mod_not_found_count}` ответов о том, что мод не найден, "
            f"и `{info.today.failed_requests_count}` ошибок."
        ),
        "",
        (
            f"За последние 7 дней было `{format_count(info.last_7_days.requests_count, ('запрос', 'запроса', 'запросов'))}`: "
            f"`{info.last_7_days.files_sent_count}` файлов и `{info.last_7_days.direct_links_count}` прямых ссылок."
        ),
        "",
        (
            f"За все время бот обработал `{format_count(info.total_requests, ('запрос', 'запроса', 'запросов'))}` "
            f"за `{format_count(info.statistics_days, ('день', 'дня', 'дней'))}`."
        ),
        (
            f"Всего отправлено `{info.total_files_sent}` файлов, `{info.total_direct_links}` прямых ссылок, "
            f"`{info.total_mod_not_found}` ответов о ненайденных модах и `{info.total_failed_requests}` ошибок."
        ),
    ]

    if info.since_date is not None:
        lines.extend(
            [
                "",
                f"Сбор статистики ведется с `{_format_iso_date(info.since_date)}`.",
            ]
        )

    lines.extend(
        [
            f"Бот находится на `{format_count(guild_count, ('сервере', 'серверах', 'серверах'))}`.",
        ]
    )
    return "\n".join(lines)


def _format_iso_date(value: str) -> str:
    try:
        return date.fromisoformat(value).strftime("%d.%m.%Y")
    except ValueError:
        return value
