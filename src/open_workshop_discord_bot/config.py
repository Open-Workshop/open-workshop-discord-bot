from __future__ import annotations

from dataclasses import dataclass, field
from json import JSONDecodeError
import json
from collections.abc import Mapping, Sequence
import os
import re
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("config.json")
DEFAULT_API_URL = "https://api.openworkshop.su"
DEFAULT_WEBSITE_URL = "https://openworkshop.su"
DEFAULT_DIRECT_DOWNLOAD_THRESHOLD_BYTES = 10 * 1024 * 1024
DEFAULT_REQUEST_TIMEOUT_SECONDS = 20.0
DEFAULT_STATISTICS_TIMEOUT_SECONDS = 10.0
DEFAULT_ACTIVITY_TYPE = "playing"
DEFAULT_ACTIVITY_NAME = "скачивание модов"
DEFAULT_STATUS = "online"
DISCORD_TOKEN_ENV_VAR = "DISCORD_TOKEN"
DEFAULT_STATISTICS_EMBED_COLOR = "#2f3136"
DEFAULT_PROJECT_EMBED_TITLE = "Это бесплатный open-source проект с открытым API! 😍"
DEFAULT_DIRECT_DOWNLOAD_BUTTON_LABEL = "Скачать"
DEFAULT_WEBSITE_BUTTON_LABEL = "Страница на сайте"
DEFAULT_CONTEXT_MENU_NAME = "Скачать мод"
ALLOWED_ACTIVITY_TYPES = {"playing", "streaming", "listening", "watching", "competing"}
ALLOWED_STATUSES = {"online", "idle", "dnd", "do_not_disturb", "invisible", "offline"}
ALLOWED_COLOR_NAMES = {"dark_gray", "dark_grey", "gray", "grey", "blurple"}
_HEX_COLOR_RE = re.compile(r"^(?:#|0x)?[0-9a-fA-F]{6}$")


class ConfigurationError(RuntimeError):
    """Raised when the bot configuration cannot be loaded or validated."""


@dataclass(frozen=True, slots=True)
class ActivityConfig:
    type: str = DEFAULT_ACTIVITY_TYPE
    name: str = DEFAULT_ACTIVITY_NAME


@dataclass(frozen=True, slots=True)
class DiscordConfig:
    activity: ActivityConfig = field(default_factory=ActivityConfig)
    status: str = DEFAULT_STATUS
    sync_commands_on_startup: bool = True


@dataclass(frozen=True, slots=True)
class ApiConfig:
    base_url: str = DEFAULT_API_URL
    website_url: str = DEFAULT_WEBSITE_URL
    direct_download_threshold_bytes: int = DEFAULT_DIRECT_DOWNLOAD_THRESHOLD_BYTES
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS
    statistics_timeout_seconds: float = DEFAULT_STATISTICS_TIMEOUT_SECONDS


@dataclass(frozen=True, slots=True)
class LinkButtonConfig:
    label: str
    url: str
    emoji: str | None = None


@dataclass(frozen=True, slots=True)
class UiConfig:
    statistics_embed_title: str = "Общая статистика"
    statistics_embed_color: str = DEFAULT_STATISTICS_EMBED_COLOR
    project_embed_title: str = DEFAULT_PROJECT_EMBED_TITLE
    project_embed_color: str = DEFAULT_STATISTICS_EMBED_COLOR
    large_mod_embed_color: str = DEFAULT_STATISTICS_EMBED_COLOR
    direct_download_button_label: str = DEFAULT_DIRECT_DOWNLOAD_BUTTON_LABEL
    website_button_label: str = DEFAULT_WEBSITE_BUTTON_LABEL
    project_buttons: tuple[LinkButtonConfig, ...] = field(
        default_factory=lambda: (
            LinkButtonConfig(
                label="GitHub проекта",
                emoji="👨‍💻",
                url="https://github.com/Open-Workshop",
            ),
            LinkButtonConfig(
                label="Discord сервер автора",
                emoji="📝",
                url="https://discord.gg/UnJnGHNbBp",
            ),
            LinkButtonConfig(
                label="Такой же бот в Telegram",
                emoji="☎",
                url="https://t.me/get_from_steam_bot",
            ),
            LinkButtonConfig(
                label="API бота",
                emoji="🤩",
                url=DEFAULT_API_URL,
            ),
            LinkButtonConfig(
                label="Сайт",
                emoji="☝",
                url=DEFAULT_WEBSITE_URL,
            ),
        )
    )


@dataclass(frozen=True, slots=True)
class MessagesConfig:
    statistics_timeout: str = "Превышено время ожидания при получении общей статистики."
    server_unavailable: str = "Похоже, что сервер не отвечает 😔"
    invalid_link: str = "Ты мне какую-то не правильную ссылку скинул! 🧐"
    need_specific_mod_link: str = "Мне нужна ссылка конкретно на мод! _(или его ID)_"
    unsupported_source: str = "Пока что я умею скачивать только c Open Workshop и ассоциированные моды со Steam 😿"
    download_prompt: str = "Если ты хочешь скачать мод, то просто скинь ссылку или `ID` мода в чат!"
    negative_mod_id: str = "Я даже без проверки знаю, что такого мода нету :)"
    download_started: str = "Сейчас пришлю..."
    download_duration_template: str = "Ваш запрос занял `{elapsed}`"
    large_mod_title_template: str = "Ого! `{name}` весит {size_mb} мегабайт!"
    large_mod_description: str = "Скачай его по прямой ссылке :smirk_cat:"
    mod_not_found: str = "На сервере нету этого мода :("
    unexpected_response: str = "Сервер прислал неожиданный ответ 😧"


@dataclass(frozen=True, slots=True)
class SlashCommandConfig:
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class CommandsConfig:
    statistics: SlashCommandConfig = field(
        default_factory=lambda: SlashCommandConfig(
            name="statistics",
            description="Небольшая статистика работы сервиса",
        )
    )
    project: SlashCommandConfig = field(
        default_factory=lambda: SlashCommandConfig(
            name="project",
            description="Информация о проекте и полезные ссылки :)",
        )
    )
    download: SlashCommandConfig = field(
        default_factory=lambda: SlashCommandConfig(
            name="download",
            description="Скачай мод напрямую с Open Workshop, передав ссылку на мод или ID мода!",
        )
    )
    context_menu_name: str = DEFAULT_CONTEXT_MENU_NAME


@dataclass(frozen=True, slots=True)
class BotConfig:
    discord_token: str
    discord: DiscordConfig
    api: ApiConfig = field(default_factory=ApiConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    messages: MessagesConfig = field(default_factory=MessagesConfig)
    commands: CommandsConfig = field(default_factory=CommandsConfig)

    @classmethod
    def from_file(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> "BotConfig":
        config_path = Path(path)
        if not config_path.exists():
            raise ConfigurationError(f"Config file '{config_path}' was not found.")

        try:
            raw_data = json.loads(config_path.read_text(encoding="utf-8"))
        except JSONDecodeError as exc:
            raise ConfigurationError(f"Config file '{config_path}' is not valid JSON.") from exc

        return cls.from_mapping(raw_data)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "BotConfig":
        if not isinstance(data, Mapping):
            raise ConfigurationError("Top-level config must be a JSON object.")

        discord_section = _require_section(data, "discord")
        if "token" in discord_section:
            raise ConfigurationError(
                "'discord.token' has been removed from config.json. "
                f"Set the {DISCORD_TOKEN_ENV_VAR} environment variable instead."
            )
        api_section = _optional_section(data, "api")
        ui_section = _optional_section(data, "ui")
        messages_section = _optional_section(data, "messages")
        commands_section = _optional_section(data, "commands")

        discord_token = _required_env_string(DISCORD_TOKEN_ENV_VAR)
        activity_section = _optional_section(discord_section, "activity")
        discord_config = DiscordConfig(
            activity=ActivityConfig(
                type=_choice_string(
                    activity_section,
                    "type",
                    DEFAULT_ACTIVITY_TYPE,
                    "discord.activity.type",
                    allowed=ALLOWED_ACTIVITY_TYPES,
                ),
                name=_string(activity_section, "name", DEFAULT_ACTIVITY_NAME, "discord.activity.name"),
            ),
            status=_choice_string(
                discord_section,
                "status",
                DEFAULT_STATUS,
                "discord.status",
                allowed=ALLOWED_STATUSES,
            ),
            sync_commands_on_startup=_bool(
                discord_section,
                "sync_commands_on_startup",
                True,
                "discord.sync_commands_on_startup",
            ),
        )

        api_config = ApiConfig(
            base_url=_string(api_section, "base_url", DEFAULT_API_URL, "api.base_url"),
            website_url=_string(api_section, "website_url", DEFAULT_WEBSITE_URL, "api.website_url"),
            direct_download_threshold_bytes=_int(
                api_section,
                "direct_download_threshold_bytes",
                DEFAULT_DIRECT_DOWNLOAD_THRESHOLD_BYTES,
                "api.direct_download_threshold_bytes",
                minimum=1,
            ),
            request_timeout_seconds=_float(
                api_section,
                "request_timeout_seconds",
                DEFAULT_REQUEST_TIMEOUT_SECONDS,
                "api.request_timeout_seconds",
                minimum=0.001,
            ),
            statistics_timeout_seconds=_float(
                api_section,
                "statistics_timeout_seconds",
                DEFAULT_STATISTICS_TIMEOUT_SECONDS,
                "api.statistics_timeout_seconds",
                minimum=0.001,
            ),
        )

        default_ui = UiConfig(
            project_buttons=_default_project_buttons(
                api_config.base_url,
                api_config.website_url,
            )
        )
        ui_config = UiConfig(
            statistics_embed_title=_string(
                ui_section,
                "statistics_embed_title",
                default_ui.statistics_embed_title,
                "ui.statistics_embed_title",
            ),
            statistics_embed_color=_string(
                ui_section,
                "statistics_embed_color",
                default_ui.statistics_embed_color,
                "ui.statistics_embed_color",
                validator=_validate_color_string,
            ),
            project_embed_title=_string(
                ui_section,
                "project_embed_title",
                default_ui.project_embed_title,
                "ui.project_embed_title",
            ),
            project_embed_color=_string(
                ui_section,
                "project_embed_color",
                default_ui.project_embed_color,
                "ui.project_embed_color",
                validator=_validate_color_string,
            ),
            large_mod_embed_color=_string(
                ui_section,
                "large_mod_embed_color",
                default_ui.large_mod_embed_color,
                "ui.large_mod_embed_color",
                validator=_validate_color_string,
            ),
            direct_download_button_label=_string(
                ui_section,
                "direct_download_button_label",
                default_ui.direct_download_button_label,
                "ui.direct_download_button_label",
            ),
            website_button_label=_string(
                ui_section,
                "website_button_label",
                default_ui.website_button_label,
                "ui.website_button_label",
            ),
            project_buttons=_parse_buttons(
                ui_section.get("project_buttons"),
                default=default_ui.project_buttons,
                path="ui.project_buttons",
            ),
        )

        default_messages = MessagesConfig()
        messages_config = MessagesConfig(
            statistics_timeout=_string(
                messages_section,
                "statistics_timeout",
                default_messages.statistics_timeout,
                "messages.statistics_timeout",
            ),
            server_unavailable=_string(
                messages_section,
                "server_unavailable",
                default_messages.server_unavailable,
                "messages.server_unavailable",
            ),
            invalid_link=_string(
                messages_section,
                "invalid_link",
                default_messages.invalid_link,
                "messages.invalid_link",
            ),
            need_specific_mod_link=_string(
                messages_section,
                "need_specific_mod_link",
                default_messages.need_specific_mod_link,
                "messages.need_specific_mod_link",
            ),
            unsupported_source=_string(
                messages_section,
                "unsupported_source",
                default_messages.unsupported_source,
                "messages.unsupported_source",
            ),
            download_prompt=_string(
                messages_section,
                "download_prompt",
                default_messages.download_prompt,
                "messages.download_prompt",
            ),
            negative_mod_id=_string(
                messages_section,
                "negative_mod_id",
                default_messages.negative_mod_id,
                "messages.negative_mod_id",
            ),
            download_started=_string(
                messages_section,
                "download_started",
                default_messages.download_started,
                "messages.download_started",
            ),
            download_duration_template=_string(
                messages_section,
                "download_duration_template",
                default_messages.download_duration_template,
                "messages.download_duration_template",
            ),
            large_mod_title_template=_string(
                messages_section,
                "large_mod_title_template",
                default_messages.large_mod_title_template,
                "messages.large_mod_title_template",
            ),
            large_mod_description=_string(
                messages_section,
                "large_mod_description",
                default_messages.large_mod_description,
                "messages.large_mod_description",
            ),
            mod_not_found=_string(
                messages_section,
                "mod_not_found",
                default_messages.mod_not_found,
                "messages.mod_not_found",
            ),
            unexpected_response=_string(
                messages_section,
                "unexpected_response",
                default_messages.unexpected_response,
                "messages.unexpected_response",
            ),
        )

        default_commands = CommandsConfig()
        commands_config = CommandsConfig(
            statistics=_parse_command(
                commands_section.get("statistics"),
                default=default_commands.statistics,
                path="commands.statistics",
            ),
            project=_parse_command(
                commands_section.get("project"),
                default=default_commands.project,
                path="commands.project",
            ),
            download=_parse_command(
                commands_section.get("download"),
                default=default_commands.download,
                path="commands.download",
            ),
            context_menu_name=_string(
                commands_section,
                "context_menu_name",
                default_commands.context_menu_name,
                "commands.context_menu_name",
            ),
        )

        return cls(
            discord_token=discord_token,
            discord=discord_config,
            api=api_config,
            ui=ui_config,
            messages=messages_config,
            commands=commands_config,
        )


def _require_section(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = data.get(name)
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"Missing or invalid '{name}' section in config.")
    return value


def _optional_section(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = data.get(name)
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"'{name}' must be a JSON object.")
    return value


def _required_string(section: Mapping[str, Any], key: str, path: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"'{path}' must be a non-empty string.")
    return value.strip()


def _required_env_string(name: str) -> str:
    value = os.getenv(name)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"Environment variable '{name}' must be set.")
    return value.strip()


def _string(
    section: Mapping[str, Any],
    key: str,
    default: str,
    path: str,
    *,
    validator: Any | None = None,
) -> str:
    value = section.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"'{path}' must be a non-empty string.")
    value = value.strip()
    if validator is not None:
        validator(value, path)
    return value


def _bool(section: Mapping[str, Any], key: str, default: bool, path: str) -> bool:
    value = section.get(key, default)
    if isinstance(value, bool):
        return value
    raise ConfigurationError(f"'{path}' must be true or false.")


def _choice_string(
    section: Mapping[str, Any],
    key: str,
    default: str,
    path: str,
    *,
    allowed: set[str],
) -> str:
    value = _string(section, key, default, path)
    if value.lower() not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise ConfigurationError(f"'{path}' must be one of: {allowed_list}.")
    return value


def _int(
    section: Mapping[str, Any],
    key: str,
    default: int,
    path: str,
    *,
    minimum: int | None = None,
) -> int:
    value = section.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigurationError(f"'{path}' must be an integer.")
    if minimum is not None and value < minimum:
        raise ConfigurationError(f"'{path}' must be at least {minimum}.")
    return value


def _float(
    section: Mapping[str, Any],
    key: str,
    default: float,
    path: str,
    *,
    minimum: float | None = None,
) -> float:
    value = section.get(key, default)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigurationError(f"'{path}' must be a number.")
    parsed = float(value)
    if minimum is not None and parsed < minimum:
        raise ConfigurationError(f"'{path}' must be at least {minimum}.")
    return parsed


def _parse_buttons(
    raw_buttons: Any,
    *,
    default: tuple[LinkButtonConfig, ...],
    path: str,
) -> tuple[LinkButtonConfig, ...]:
    if raw_buttons is None:
        return default
    if not isinstance(raw_buttons, Sequence) or isinstance(raw_buttons, (str, bytes, bytearray)):
        raise ConfigurationError(f"'{path}' must be a JSON array.")

    buttons: list[LinkButtonConfig] = []
    for index, item in enumerate(raw_buttons):
        if not isinstance(item, Mapping):
            raise ConfigurationError(f"'{path}[{index}]' must be a JSON object.")

        label = item.get("label")
        url = item.get("url")
        emoji = item.get("emoji")

        if not isinstance(label, str) or not label.strip():
            raise ConfigurationError(f"'{path}[{index}].label' must be a non-empty string.")
        if not isinstance(url, str) or not url.strip():
            raise ConfigurationError(f"'{path}[{index}].url' must be a non-empty string.")
        if emoji is not None and (not isinstance(emoji, str) or not emoji.strip()):
            raise ConfigurationError(f"'{path}[{index}].emoji' must be a non-empty string when present.")

        buttons.append(
            LinkButtonConfig(
                label=label.strip(),
                url=url.strip(),
                emoji=emoji.strip() if isinstance(emoji, str) else None,
            )
        )

    return tuple(buttons)


def _parse_command(
    raw_command: Any,
    *,
    default: SlashCommandConfig,
    path: str,
) -> SlashCommandConfig:
    if raw_command is None:
        return default
    if not isinstance(raw_command, Mapping):
        raise ConfigurationError(f"'{path}' must be a JSON object.")

    name = raw_command.get("name", default.name)
    description = raw_command.get("description", default.description)

    if not isinstance(name, str) or not name.strip():
        raise ConfigurationError(f"'{path}.name' must be a non-empty string.")
    if not isinstance(description, str) or not description.strip():
        raise ConfigurationError(f"'{path}.description' must be a non-empty string.")

    return SlashCommandConfig(name=name.strip(), description=description.strip())


def _validate_color_string(value: str, path: str) -> None:
    normalized = value.strip().lower()
    if normalized in ALLOWED_COLOR_NAMES:
        return
    if _HEX_COLOR_RE.fullmatch(value.strip()):
        return
    raise ConfigurationError(
        f"'{path}' must be a named color or a 6-digit hex color like #2f3136."
    )


def _default_project_buttons(
    api_base_url: str,
    website_url: str,
) -> tuple[LinkButtonConfig, ...]:
    return (
        LinkButtonConfig(
            label="GitHub проекта",
            emoji="👨‍💻",
            url="https://github.com/Open-Workshop",
        ),
        LinkButtonConfig(
            label="Discord сервер автора",
            emoji="📝",
            url="https://discord.gg/UnJnGHNbBp",
        ),
        LinkButtonConfig(
            label="Такой же бот в Telegram",
            emoji="☎",
            url="https://t.me/get_from_steam_bot",
        ),
        LinkButtonConfig(
            label="API бота",
            emoji="🤩",
            url=api_base_url,
        ),
        LinkButtonConfig(
            label="Сайт",
            emoji="☝",
            url=website_url,
        ),
    )
