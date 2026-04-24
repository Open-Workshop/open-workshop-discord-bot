from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError
import json
from collections.abc import Mapping, Sequence
import os
import re
from pathlib import Path
from typing import Any


CONFIG_PATH = Path("config.json")
DISCORD_TOKEN_ENV_VAR = "DISCORD_TOKEN"
ALLOWED_ACTIVITY_TYPES = {"playing", "streaming", "listening", "watching", "competing"}
ALLOWED_STATUSES = {"online", "idle", "dnd", "do_not_disturb", "invisible", "offline"}
ALLOWED_COLOR_NAMES = {"dark_gray", "dark_grey", "gray", "grey", "blurple"}
_HEX_COLOR_RE = re.compile(r"^(?:#|0x)?[0-9a-fA-F]{6}$")


class ConfigurationError(RuntimeError):
    """Raised when the bot configuration cannot be loaded or validated."""


@dataclass(frozen=True, slots=True)
class ActivityConfig:
    type: str
    name: str


@dataclass(frozen=True, slots=True)
class DiscordConfig:
    activity: ActivityConfig
    status: str
    sync_commands_on_startup: bool


@dataclass(frozen=True, slots=True)
class ApiConfig:
    base_url: str
    website_url: str
    direct_download_threshold_bytes: int
    request_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class StorageConfig:
    database_path: str


@dataclass(frozen=True, slots=True)
class LinkButtonConfig:
    label: str
    url: str
    emoji: str | None


@dataclass(frozen=True, slots=True)
class UiConfig:
    statistics_embed_title: str
    statistics_embed_color: str
    project_embed_title: str
    project_embed_color: str
    large_mod_embed_color: str
    direct_download_button_label: str
    website_button_label: str
    project_buttons: tuple[LinkButtonConfig, ...]


@dataclass(frozen=True, slots=True)
class MessagesConfig:
    server_unavailable: str
    invalid_link: str
    need_specific_mod_link: str
    unsupported_source: str
    download_prompt: str
    negative_mod_id: str
    download_started: str
    download_duration_template: str
    large_mod_title_template: str
    large_mod_description: str
    mod_not_found: str
    unexpected_response: str


@dataclass(frozen=True, slots=True)
class SlashCommandConfig:
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class CommandsConfig:
    statistics: SlashCommandConfig
    project: SlashCommandConfig
    download: SlashCommandConfig
    context_menu_name: str


@dataclass(frozen=True, slots=True)
class BotConfig:
    discord_token: str
    discord: DiscordConfig
    api: ApiConfig
    storage: StorageConfig
    ui: UiConfig
    messages: MessagesConfig
    commands: CommandsConfig

    @classmethod
    def from_file(cls, path: str | Path = CONFIG_PATH) -> "BotConfig":
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
        api_section = _require_section(data, "api")
        storage_section = _require_section(data, "storage")
        ui_section = _require_section(data, "ui")
        messages_section = _require_section(data, "messages")
        commands_section = _require_section(data, "commands")

        discord_token = _required_env_string(DISCORD_TOKEN_ENV_VAR)
        activity_section = _require_section(discord_section, "activity")
        discord_config = DiscordConfig(
            activity=ActivityConfig(
                type=_required_choice_string(
                    activity_section,
                    "type",
                    "discord.activity.type",
                    allowed=ALLOWED_ACTIVITY_TYPES,
                ),
                name=_required_string(activity_section, "name", "discord.activity.name"),
            ),
            status=_required_choice_string(
                discord_section,
                "status",
                "discord.status",
                allowed=ALLOWED_STATUSES,
            ),
            sync_commands_on_startup=_required_bool(
                discord_section,
                "sync_commands_on_startup",
                "discord.sync_commands_on_startup",
            ),
        )

        api_config = ApiConfig(
            base_url=_required_string(api_section, "base_url", "api.base_url"),
            website_url=_required_string(api_section, "website_url", "api.website_url"),
            direct_download_threshold_bytes=_required_int(
                api_section,
                "direct_download_threshold_bytes",
                "api.direct_download_threshold_bytes",
                minimum=1,
            ),
            request_timeout_seconds=_required_float(
                api_section,
                "request_timeout_seconds",
                "api.request_timeout_seconds",
                minimum=0.001,
            ),
        )
        storage_config = StorageConfig(
            database_path=_required_string(
                storage_section,
                "database_path",
                "storage.database_path",
            ),
        )

        ui_config = UiConfig(
            statistics_embed_title=_required_string(
                ui_section,
                "statistics_embed_title",
                "ui.statistics_embed_title",
            ),
            statistics_embed_color=_required_string(
                ui_section,
                "statistics_embed_color",
                "ui.statistics_embed_color",
                validator=_validate_color_string,
            ),
            project_embed_title=_required_string(
                ui_section,
                "project_embed_title",
                "ui.project_embed_title",
            ),
            project_embed_color=_required_string(
                ui_section,
                "project_embed_color",
                "ui.project_embed_color",
                validator=_validate_color_string,
            ),
            large_mod_embed_color=_required_string(
                ui_section,
                "large_mod_embed_color",
                "ui.large_mod_embed_color",
                validator=_validate_color_string,
            ),
            direct_download_button_label=_required_string(
                ui_section,
                "direct_download_button_label",
                "ui.direct_download_button_label",
            ),
            website_button_label=_required_string(
                ui_section,
                "website_button_label",
                "ui.website_button_label",
            ),
            project_buttons=_parse_buttons(
                _required_sequence(ui_section, "project_buttons", "ui.project_buttons"),
                path="ui.project_buttons",
            ),
        )

        messages_config = MessagesConfig(
            server_unavailable=_required_string(
                messages_section,
                "server_unavailable",
                "messages.server_unavailable",
            ),
            invalid_link=_required_string(
                messages_section,
                "invalid_link",
                "messages.invalid_link",
            ),
            need_specific_mod_link=_required_string(
                messages_section,
                "need_specific_mod_link",
                "messages.need_specific_mod_link",
            ),
            unsupported_source=_required_string(
                messages_section,
                "unsupported_source",
                "messages.unsupported_source",
            ),
            download_prompt=_required_string(
                messages_section,
                "download_prompt",
                "messages.download_prompt",
            ),
            negative_mod_id=_required_string(
                messages_section,
                "negative_mod_id",
                "messages.negative_mod_id",
            ),
            download_started=_required_string(
                messages_section,
                "download_started",
                "messages.download_started",
            ),
            download_duration_template=_required_string(
                messages_section,
                "download_duration_template",
                "messages.download_duration_template",
            ),
            large_mod_title_template=_required_string(
                messages_section,
                "large_mod_title_template",
                "messages.large_mod_title_template",
            ),
            large_mod_description=_required_string(
                messages_section,
                "large_mod_description",
                "messages.large_mod_description",
            ),
            mod_not_found=_required_string(
                messages_section,
                "mod_not_found",
                "messages.mod_not_found",
            ),
            unexpected_response=_required_string(
                messages_section,
                "unexpected_response",
                "messages.unexpected_response",
            ),
        )

        commands_config = CommandsConfig(
            statistics=_parse_command(
                _require_section(commands_section, "statistics"),
                path="commands.statistics",
            ),
            project=_parse_command(
                _require_section(commands_section, "project"),
                path="commands.project",
            ),
            download=_parse_command(
                _require_section(commands_section, "download"),
                path="commands.download",
            ),
            context_menu_name=_required_string(
                commands_section,
                "context_menu_name",
                "commands.context_menu_name",
            ),
        )

        return cls(
            discord_token=discord_token,
            discord=discord_config,
            api=api_config,
            storage=storage_config,
            ui=ui_config,
            messages=messages_config,
            commands=commands_config,
        )


def _require_section(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = data.get(name)
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"Missing or invalid '{name}' section in config.")
    return value


def _required_string(
    section: Mapping[str, Any],
    key: str,
    path: str,
    *,
    validator: Any | None = None,
) -> str:
    if key not in section:
        raise ConfigurationError(f"'{path}' is required.")
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"'{path}' must be a non-empty string.")
    parsed = value.strip()
    if validator is not None:
        validator(parsed, path)
    return parsed


def _required_env_string(name: str) -> str:
    value = os.getenv(name)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"Environment variable '{name}' must be set.")
    return value.strip()


def _required_bool(section: Mapping[str, Any], key: str, path: str) -> bool:
    if key not in section:
        raise ConfigurationError(f"'{path}' is required.")
    value = section.get(key)
    if isinstance(value, bool):
        return value
    raise ConfigurationError(f"'{path}' must be true or false.")


def _required_choice_string(
    section: Mapping[str, Any],
    key: str,
    path: str,
    *,
    allowed: set[str],
) -> str:
    value = _required_string(section, key, path)
    if value.lower() not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise ConfigurationError(f"'{path}' must be one of: {allowed_list}.")
    return value


def _required_int(
    section: Mapping[str, Any],
    key: str,
    path: str,
    *,
    minimum: int | None = None,
) -> int:
    if key not in section:
        raise ConfigurationError(f"'{path}' is required.")
    value = section.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigurationError(f"'{path}' must be an integer.")
    if minimum is not None and value < minimum:
        raise ConfigurationError(f"'{path}' must be at least {minimum}.")
    return value


def _required_float(
    section: Mapping[str, Any],
    key: str,
    path: str,
    *,
    minimum: float | None = None,
) -> float:
    if key not in section:
        raise ConfigurationError(f"'{path}' is required.")
    value = section.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigurationError(f"'{path}' must be a number.")
    parsed = float(value)
    if minimum is not None and parsed < minimum:
        raise ConfigurationError(f"'{path}' must be at least {minimum}.")
    return parsed


def _required_sequence(
    section: Mapping[str, Any],
    key: str,
    path: str,
) -> Sequence[Any]:
    if key not in section:
        raise ConfigurationError(f"'{path}' is required.")
    value = section.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ConfigurationError(f"'{path}' must be a JSON array.")
    if len(value) == 0:
        raise ConfigurationError(f"'{path}' must not be empty.")
    return value


def _parse_buttons(
    raw_buttons: Any,
    *,
    path: str,
) -> tuple[LinkButtonConfig, ...]:
    if not isinstance(raw_buttons, Sequence) or isinstance(raw_buttons, (str, bytes, bytearray)):
        raise ConfigurationError(f"'{path}' must be a JSON array.")
    if len(raw_buttons) == 0:
        raise ConfigurationError(f"'{path}' must not be empty.")

    buttons: list[LinkButtonConfig] = []
    for index, item in enumerate(raw_buttons):
        if not isinstance(item, Mapping):
            raise ConfigurationError(f"'{path}[{index}]' must be a JSON object.")

        if "label" not in item:
            raise ConfigurationError(f"'{path}[{index}].label' is required.")
        if "url" not in item:
            raise ConfigurationError(f"'{path}[{index}].url' is required.")
        if "emoji" not in item:
            raise ConfigurationError(f"'{path}[{index}].emoji' is required.")

        buttons.append(
            LinkButtonConfig(
                label=_required_string(item, "label", f"{path}[{index}].label"),
                url=_required_string(item, "url", f"{path}[{index}].url"),
                emoji=_required_emoji(item, "emoji", f"{path}[{index}].emoji"),
            )
        )

    return tuple(buttons)


def _parse_command(
    raw_command: Any,
    *,
    path: str,
) -> SlashCommandConfig:
    if not isinstance(raw_command, Mapping):
        raise ConfigurationError(f"'{path}' must be a JSON object.")

    name = _required_string(raw_command, "name", f"{path}.name")
    description = _required_string(raw_command, "description", f"{path}.description")

    return SlashCommandConfig(name=name, description=description)


def _validate_color_string(value: str, path: str) -> None:
    normalized = value.strip().lower()
    if normalized in ALLOWED_COLOR_NAMES:
        return
    if _HEX_COLOR_RE.fullmatch(value.strip()):
        return
    raise ConfigurationError(
        f"'{path}' must be a named color or a 6-digit hex color like #2f3136."
    )


def _required_emoji(section: Mapping[str, Any], key: str, path: str) -> str | None:
    value = section.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"'{path}' must be a non-empty string or null.")
    return value.strip()
