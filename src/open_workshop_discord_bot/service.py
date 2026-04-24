from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Literal

import aiohttp

from .utils import extract_download_filename


class OpenWorkshopError(RuntimeError):
    """Base exception for Open Workshop API issues."""


class OpenWorkshopResponseError(OpenWorkshopError):
    """Raised when the API returns a response that does not match expectations."""


class OpenWorkshopNotFoundError(OpenWorkshopError):
    """Raised when the API reports that a requested resource does not exist."""


@dataclass(slots=True)
class DownloadResponse:
    kind: Literal["zip", "json", "other"]
    content_type: str
    data: bytes = b""
    json_data: dict[str, Any] | None = None
    filename: str | None = None


class OpenWorkshopAPI:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        *,
        request_timeout_seconds: float,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._request_timeout = aiohttp.ClientTimeout(total=request_timeout_seconds)

    async def fetch_mod_info(self, mod_id: int) -> dict[str, Any]:
        return await self._fetch_json(f"mods/{mod_id}", timeout=self._request_timeout)

    async def fetch_download(self, mod_id: int) -> DownloadResponse:
        url = self._make_url(f"mods/{mod_id}/download")
        async with self._session.get(url, timeout=self._request_timeout) as response:
            if response.status == 404:
                raise OpenWorkshopNotFoundError("Open Workshop mod was not found.")

            content_type = response.headers.get("content-type", "")

            if content_type.startswith("application/zip"):
                return DownloadResponse(
                    kind="zip",
                    content_type=content_type,
                    data=await response.read(),
                    filename=extract_download_filename(
                        response.headers.get("content-disposition"),
                        fallback=f"mod-{mod_id}.zip",
                    ),
                )

            if content_type.startswith("application/json"):
                return DownloadResponse(
                    kind="json",
                    content_type=content_type,
                    json_data=await self._read_json(response),
                )

            return DownloadResponse(
                kind="other",
                content_type=content_type,
                data=await response.read(),
            )

    async def _fetch_json(
        self,
        path: str,
        *,
        timeout: aiohttp.ClientTimeout,
    ) -> dict[str, Any]:
        url = self._make_url(path)
        async with self._session.get(url, timeout=timeout) as response:
            if response.status == 404:
                raise OpenWorkshopNotFoundError("Open Workshop mod was not found.")
            return await self._read_json(response)

    async def _read_json(self, response: aiohttp.ClientResponse) -> dict[str, Any]:
        raw_text = await response.text()
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise OpenWorkshopResponseError("Open Workshop returned a non-JSON response.") from exc

        if not isinstance(payload, dict):
            raise OpenWorkshopResponseError("Open Workshop returned JSON that is not an object.")

        return payload

    def _make_url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"
