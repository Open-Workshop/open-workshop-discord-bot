from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse
import re


_FILENAME_CLEANUP_RE = re.compile(r"[\\/\x00-\x1f]+")


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
    value = raw_value.strip()
    if not value:
        return None
    if value.isdigit():
        return value

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return None

    host = parsed.netloc.lower()
    path = parsed.path.strip("/")

    if host.endswith("steamcommunity.com"):
        if path in {"sharedfiles/filedetails", "workshop/filedetails"}:
            mod_id = parse_qs(parsed.query).get("id", [""])[0].strip()
            return mod_id if mod_id.isdigit() else None
        return None

    if host.endswith("openworkshop.su") and path.startswith("mod/"):
        mod_id = path.removeprefix("mod/").split("/", 1)[0]
        return mod_id if mod_id.isdigit() else None

    return None


def explain_invalid_workshop_link(raw_value: str) -> str:
    value = raw_value.strip()
    parsed = urlparse(value)
    host = parsed.netloc.lower()

    if parsed.scheme in {"http", "https"} and host.endswith(
        ("steamcommunity.com", "openworkshop.su", "store.steampowered.com")
    ):
        if host.endswith(("steamcommunity.com", "openworkshop.su")):
            return "Мне нужна ссылка конкретно на мод! _(или его ID)_"
        return "Пока что я умею скачивать только c Open Workshop и ассоциированные моды со Steam 😿"

    if parsed.scheme in {"http", "https"}:
        return "Пока что я умею скачивать только c Open Workshop и ассоциированные моды со Steam 😿"

    return "Если ты хочешь скачать мод, то просто скинь ссылку или `ID` мода в чат!"


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
