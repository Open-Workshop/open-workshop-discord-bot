from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal
from urllib.parse import parse_qs, unquote, urlparse

import discord

from .config import MessagesConfig


_FILENAME_CLEANUP_RE = re.compile(r"[\\/\x00-\x1f]+")
_FACTORIO_MOD_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_FACTORIO_RESERVED_NAMES = {
    "changelog",
    "dependencies",
    "discussion",
    "download",
    "downloads",
    "factorio",
    "http",
    "https",
    "information",
    "metrics",
    "mod",
    "mods",
    "openworkshop",
    "steam",
}
_DISCORD_NAMED_COLOR_VALUES = {
    "dark_gray": 0x607D8B,
    "dark_grey": 0x607D8B,
    # discord.py has no plain gray()/grey(); keep these config aliases on greyple.
    "gray": 0x99AAB5,
    "grey": 0x99AAB5,
    "blurple": 0x5865F2,
}


@dataclass(frozen=True, slots=True)
class WorkshopReference:
    id: int | str
    kind: Literal["openworkshop", "steam", "factorio", "unknown"]


def format_count(number: int, forms: tuple[str, str, str]) -> str:
    return f"{number} {pluralize_ru(number, forms)}"


def format_duration(seconds: float) -> str:
    value = round(seconds, 1)
    if float(value).is_integer():
        return format_count(int(value), ("секунда", "секунды", "секунд"))
    return f"{value:g} секунды"


def pluralize_ru(number: int, forms: tuple[str, str, str]) -> str:
    if len(forms) != 3:
        raise ValueError("Russian pluralization requires three word forms.")

    number = abs(int(number))
    if 11 <= number % 100 <= 14:
        return forms[2]
    if number % 10 == 1:
        return forms[0]
    if 2 <= number % 10 <= 4:
        return forms[1]
    return forms[2]


def parse_workshop_id(raw_value: str) -> str | None:
    reference = parse_workshop_reference(raw_value)
    if reference is None:
        return None
    return str(reference.id)


def parse_workshop_reference(raw_value: str) -> WorkshopReference | None:
    value = raw_value.strip()
    if not value:
        return None
    if value.isdigit():
        return WorkshopReference(id=int(value), kind="unknown")
    if value.lower() not in _FACTORIO_RESERVED_NAMES and _FACTORIO_MOD_NAME_RE.fullmatch(value):
        return WorkshopReference(id=value, kind="factorio")

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return None

    host = parsed.netloc.lower()
    path = parsed.path.strip("/")

    if host.endswith("steamcommunity.com"):
        if path in {"sharedfiles/filedetails", "workshop/filedetails"}:
            mod_id = parse_qs(parsed.query).get("id", [""])[0].strip()
            if mod_id.isdigit():
                return WorkshopReference(id=int(mod_id), kind="steam")
            return None
        return None

    if host.endswith("mods.factorio.com"):
        mod_name = _extract_factorio_mod_name(path)
        if mod_name is not None:
            return WorkshopReference(id=mod_name, kind="factorio")
        return None

    query_id = parse_qs(parsed.query).get("id", [""])[0].strip()
    if path.startswith("mod/"):
        mod_id = path.removeprefix("mod/").split("/", 1)[0]
    elif path.startswith("mods/"):
        mod_id = path.removeprefix("mods/").split("/", 1)[0]
    elif query_id:
        mod_id = query_id
    else:
        mod_id = ""

    if path.startswith(("mod/", "mods/")) or query_id:
        if mod_id.isdigit():
            return WorkshopReference(id=int(mod_id), kind="openworkshop")
        return None

    return None


def explain_invalid_workshop_link(raw_value: str, messages: MessagesConfig) -> str:
    value = raw_value.strip()
    if not value:
        return messages.invalid_link

    parsed = urlparse(value)
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")

    if parsed.scheme in {"http", "https"}:
        if path.startswith(("mod/", "mods/")):
            return messages.need_specific_mod_link
        if host.endswith("steamcommunity.com") and path in {"sharedfiles/filedetails", "workshop/filedetails"}:
            return messages.need_specific_mod_link
        if host.endswith("mods.factorio.com") and path.startswith(("mod/", "mods/")):
            return messages.need_specific_mod_link
        return messages.unsupported_source

    return messages.download_prompt


def extract_download_filename(content_disposition: str | None, fallback: str) -> str:
    if not content_disposition:
        return sanitize_filename(fallback, fallback)

    filename = ""
    for item in (part.strip() for part in content_disposition.split(";")):
        key, separator, value = item.partition("=")
        if not separator:
            continue

        key = key.strip().lower()
        value = value.strip().strip('"')

        if key == "filename*":
            if "''" in value:
                value = value.split("''", 1)[1]
            filename = unquote(value)
            break

        if key == "filename" and not filename:
            filename = unquote(value)

    return sanitize_filename(filename or fallback, fallback)


def sanitize_filename(filename: str, fallback: str) -> str:
    cleaned = _FILENAME_CLEANUP_RE.sub("_", filename).strip().strip(".")
    return cleaned or fallback


def parse_discord_color(value: str | int) -> discord.Color:
    if isinstance(value, int):
        return discord.Color(value)

    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("Color value cannot be empty.")

    if normalized in _DISCORD_NAMED_COLOR_VALUES:
        return discord.Color(_DISCORD_NAMED_COLOR_VALUES[normalized])

    if normalized.startswith("#"):
        normalized = normalized[1:]
    if normalized.startswith("0x"):
        normalized = normalized[2:]

    if len(normalized) != 6:
        raise ValueError(f"Unsupported color value: {value!r}")

    return discord.Color(int(normalized, 16))


def _extract_factorio_mod_name(path: str) -> str | None:
    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return None

    if segments[0] == "mod":
        candidate = segments[1] if len(segments) > 1 else ""
    elif segments[0] == "mods":
        if len(segments) == 2:
            candidate = segments[1]
        elif len(segments) == 3:
            candidate = segments[1] if segments[2] in _FACTORIO_SUBPAGES else segments[2]
        else:
            candidate = segments[-2] if segments[-1] in _FACTORIO_SUBPAGES else segments[-1]
    else:
        return None

    return candidate if candidate and _FACTORIO_MOD_NAME_RE.fullmatch(candidate) else None


_FACTORIO_SUBPAGES = {
    "changelog",
    "dependencies",
    "discussion",
    "downloads",
    "information",
    "metrics",
}
