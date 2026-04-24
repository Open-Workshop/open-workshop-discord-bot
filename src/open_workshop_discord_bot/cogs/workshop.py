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

from ..service import OpenWorkshopError
from ..utils import (
    explain_invalid_workshop_link,
    format_count,
    format_duration,
    parse_workshop_id,
)

if TYPE_CHECKING:
    from ..bot import WorkshopBot


LOGGER = logging.getLogger(__name__)


class WorkshopCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._download_context_menu = app_commands.ContextMenu(
            name="Скачать мод",
            callback=self.download_from_message_context,
        )

    async def cog_load(self) -> None:
        self.bot.tree.add_command(self._download_context_menu)

    def cog_unload(self) -> None:
        self.bot.tree.remove_command(
            self._download_context_menu.name,
            type=self._download_context_menu.type,
        )

    @property
    def _typed_bot(self) -> "WorkshopBot":
        return cast("WorkshopBot", self.bot)

    @property
    def api(self):
        return self._typed_bot.api_client

    @property
    def settings(self):
        return self._typed_bot.settings

    @app_commands.command(
        name="statistics",
        description="Небольшая статистика работы сервиса",
    )
    async def statistics(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        try:
            info = await self.api.fetch_statistics()
        except asyncio.TimeoutError:
            await interaction.followup.send(
                "Превышено время ожидания при получении общей статистики."
            )
            return
        except (aiohttp.ClientError, OpenWorkshopError):
            await interaction.followup.send("Похоже, что сервер не отвечает 😔")
            return

        embed = discord.Embed(
            title="Общая статистика",
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
            color=discord.Color.dark_gray(),
        )

        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="project",
        description="Информация о проекте и полезные ссылки :)",
    )
    async def project(self, interaction: discord.Interaction) -> None:
        view = discord.ui.View()
        for label, emoji, url in (
            ("GitHub проекта", "👨‍💻", "https://github.com/Open-Workshop"),
            ("Discord сервер автора", "📝", "https://discord.gg/UnJnGHNbBp"),
            ("Такой же бот в Telegram", "☎", "https://t.me/get_from_steam_bot"),
            ("API бота", "🤩", self.settings.api_url),
            ("Сайт", "☝", self.settings.website_url),
        ):
            view.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    emoji=emoji,
                    label=label,
                    url=url,
                )
            )

        embed = discord.Embed(
            title="Это бесплатный open-source проект с открытым API! 😍",
            color=discord.Color.dark_gray(),
        )
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(
        name="download",
        description="Скачай мод напрямую с Open Workshop, передав ссылку на мод или ID мода!",
    )
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
            await interaction.followup.send(explain_invalid_workshop_link(raw_link))
            return

        mod_id = int(mod_id_text)
        if mod_id <= 0:
            await interaction.followup.send("Я даже без проверки знаю, что такого мода нету :)")
            return

        try:
            mod_info = await self.api.fetch_mod_info(mod_id)
        except asyncio.TimeoutError:
            await interaction.followup.send("Похоже, что сервер не отвечает 😔")
            return
        except (aiohttp.ClientError, OpenWorkshopError):
            await interaction.followup.send("Похоже, что сервер не отвечает 😔")
            return

        result = mod_info.get("result")
        if isinstance(result, dict):
            try:
                size_bytes = int(result.get("size", 0) or 0)
            except (TypeError, ValueError):
                size_bytes = 0

            if size_bytes > self.settings.direct_download_threshold_bytes:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title=(
                            f"Ого! `{result.get('name', mod_id)}` весит "
                            f"{round(size_bytes / 1024 / 1024, 1)} мегабайт!"
                        ),
                        description="Скачай его по прямой ссылке :smirk_cat:",
                        color=discord.Color.dark_gray(),
                    ),
                    view=self._build_mod_links_view(mod_id, include_direct_download=True),
                )
                return

        try:
            download = await self.api.fetch_download(mod_id)
        except asyncio.TimeoutError:
            await interaction.followup.send("Похоже, что сервер не отвечает 😔")
            return
        except (aiohttp.ClientError, OpenWorkshopError):
            await interaction.followup.send("Похоже, что сервер не отвечает 😔")
            return

        if download.kind == "zip" and download.data:
            elapsed = format_duration(time.perf_counter() - started_at)
            await interaction.followup.send(
                content=f"Ваш запрос занял `{elapsed}`",
                file=discord.File(
                    BytesIO(download.data),
                    filename=download.filename or f"mod-{mod_id}.zip",
                ),
                view=self._build_mod_links_view(mod_id, include_direct_download=False),
            )
            return

        if download.kind == "json" and isinstance(download.json_data, dict):
            if download.json_data.get("error_id") in {0, 2, 3}:
                await interaction.followup.send("На сервере нету этого мода :(")
            else:
                await interaction.followup.send("Сервер прислал неожиданный ответ 😧")
            return

        LOGGER.warning(
            "Unexpected download response for mod %s with content type %s",
            mod_id,
            download.content_type,
        )
        await interaction.followup.send("Сервер прислал неожиданный ответ 😧")

    def _build_mod_links_view(self, mod_id: int, *, include_direct_download: bool) -> discord.ui.View:
        view = discord.ui.View()

        if include_direct_download:
            view.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    label="Скачать",
                    url=f"{self.settings.api_url}/download/{mod_id}",
                )
            )

        view.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Страница на сайте",
                url=f"{self.settings.website_url}/mod/{mod_id}",
            )
        )
        return view
