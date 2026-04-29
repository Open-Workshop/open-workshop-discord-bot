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
        return await self._request_json(
            "GET",
            f"mods/{mod_id}",
            timeout=self._request_timeout,
        )

    async def fetch_mod_info_by_source_id(
        self,
        source: str,
        source_id: int,
    ) -> tuple[int, dict[str, Any]]:
        payload = await self._request_json(
            "GET",
            "mods",
            timeout=self._request_timeout,
            params={
                "page_size": 1,
                "page": 0,
                "sources": [source],
                "source_ids": [source_id],
            },
        )

        items = payload.get("items")
        if not isinstance(items, list):
            raise OpenWorkshopResponseError("Open Workshop returned a mod list without items.")

        if not items:
            raise OpenWorkshopNotFoundError("Open Workshop mod was not found by source id.")

        first_item = items[0]
        if not isinstance(first_item, dict):
            raise OpenWorkshopResponseError("Open Workshop returned a mod list item that is not an object.")

        mod_id = _parse_positive_int(first_item.get("id"))
        if mod_id is None:
            raise OpenWorkshopResponseError("Open Workshop returned a mod without an id.")
        return mod_id, first_item

    async def fetch_download(self, mod_id: int) -> DownloadResponse:
        download_info = await self._request_json(
            "POST",
            f"mods/{mod_id}/download-url",
            timeout=self._request_timeout,
            expected_statuses={200, 201},
        )

        download_url = download_info.get("download_url")
        if not isinstance(download_url, str) or not download_url.strip():
            raise OpenWorkshopResponseError("Open Workshop returned a download-url response without download_url.")

        fallback_filename = download_info.get("filename")
        if not isinstance(fallback_filename, str) or not fallback_filename.strip():
            fallback_filename = f"mod-{mod_id}.zip"

        async with self._session.get(download_url, timeout=self._request_timeout) as response:
            if response.status == 404:
                raise OpenWorkshopNotFoundError("Open Workshop mod was not found.")

            content_type = response.headers.get("content-type", "")
            if response.status != 200:
                payload = await self._try_read_json(response)
                if payload is not None and _extract_problem_code(payload) in {"NOT_FOUND", "MOD_NOT_FOUND"}:
                    raise OpenWorkshopNotFoundError("Open Workshop mod was not found.")
                raise OpenWorkshopResponseError(
                    f"Open Workshop returned an unexpected download status code: {response.status}."
                )

            if content_type.startswith("application/json"):
                payload = await self._try_read_json(response)
                if payload is not None and _extract_problem_code(payload) in {"NOT_FOUND", "MOD_NOT_FOUND"}:
                    raise OpenWorkshopNotFoundError("Open Workshop mod was not found.")
                raise OpenWorkshopResponseError("Open Workshop returned JSON instead of a download archive.")

            return DownloadResponse(
                kind="zip",
                content_type=content_type,
                data=await response.read(),
                filename=extract_download_filename(
                    response.headers.get("content-disposition"),
                    fallback=fallback_filename,
                ),
            )

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        timeout: aiohttp.ClientTimeout,
        expected_statuses: set[int] | frozenset[int] | tuple[int, ...] = (200,),
        params: dict[str, Any] | None = None,
        data: Any | None = None,
    ) -> dict[str, Any]:
        url = self._make_url(path)
        async with self._session.request(
            method,
            url,
            timeout=timeout,
            params=params,
            data=data,
        ) as response:
            if response.status == 404:
                raise OpenWorkshopNotFoundError("Open Workshop mod was not found.")
            payload = await self._read_json(response)
            if response.status not in expected_statuses:
                if _extract_problem_code(payload) in {"NOT_FOUND", "MOD_NOT_FOUND"}:
                    raise OpenWorkshopNotFoundError("Open Workshop mod was not found.")
                raise OpenWorkshopResponseError(
                    f"Open Workshop returned an unexpected status code: {response.status}."
                )
            return payload

    async def _read_json(self, response: aiohttp.ClientResponse) -> dict[str, Any]:
        raw_text = await response.text()
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise OpenWorkshopResponseError("Open Workshop returned a non-JSON response.") from exc

        if not isinstance(payload, dict):
            raise OpenWorkshopResponseError("Open Workshop returned JSON that is not an object.")

        return payload

    async def _try_read_json(self, response: aiohttp.ClientResponse) -> dict[str, Any] | None:
        try:
            return await self._read_json(response)
        except OpenWorkshopResponseError:
            return None

    def _make_url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"


def _parse_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _extract_problem_code(payload: dict[str, Any]) -> str | None:
    code = payload.get("code")
    if isinstance(code, str) and code.strip():
        return code.strip()
    return None
