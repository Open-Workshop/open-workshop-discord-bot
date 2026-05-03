from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

if "discord" not in sys.modules:
    discord_stub = types.ModuleType("discord")
    discord_stub.Color = type("Color", (), {"__init__": lambda self, value=0: setattr(self, "value", value)})
    sys.modules["discord"] = discord_stub

from open_workshop_discord_bot.service import OpenWorkshopAPI


class _DummyResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        json_payload: object | None = None,
        read_payload: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._json_payload = json_payload
        self._read_payload = read_payload
        self.headers = headers or {}

    async def __aenter__(self) -> "_DummyResponse":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def text(self) -> str:
        if self._json_payload is not None:
            return json.dumps(self._json_payload)
        return self._read_payload.decode("utf-8", errors="replace")

    async def read(self) -> bytes:
        return self._read_payload


class _DummySession:
    def __init__(self, responses: dict[tuple[str, str], _DummyResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def request(self, method: str, url: str, **kwargs) -> _DummyResponse:
        self.calls.append((method, url, dict(kwargs)))
        return self.responses[(method, url)]

    def get(self, url: str, **kwargs) -> _DummyResponse:
        self.calls.append(("GET", url, dict(kwargs)))
        return self.responses[("GET", url)]


class OpenWorkshopServiceTests(unittest.TestCase):
    def test_fetch_mod_info_uses_direct_object_payload(self) -> None:
        session = _DummySession(
            {
                ("GET", "https://api.example/mods/784"): _DummyResponse(
                    status=200,
                    json_payload={"id": 784, "name": "Wolfein Race", "size": 1234},
                )
            }
        )
        api = OpenWorkshopAPI(session, "https://api.example", request_timeout_seconds=5)

        payload = asyncio.run(api.fetch_mod_info(784))

        self.assertEqual(payload["id"], 784)
        self.assertEqual(payload["name"], "Wolfein Race")
        self.assertEqual(session.calls[0][0], "GET")
        self.assertEqual(session.calls[0][1], "https://api.example/mods/784")

    def test_fetch_mod_info_by_source_id_uses_items_response(self) -> None:
        session = _DummySession(
            {
                ("GET", "https://api.example/mods"): _DummyResponse(
                    status=200,
                    json_payload={
                        "items": [
                            {
                                "id": 784,
                                "name": "Wolfein Race",
                                "size": 1234,
                                "source": "steam",
                                "source_id": 3701480464,
                            }
                        ]
                    },
                )
            }
        )
        api = OpenWorkshopAPI(session, "https://api.example", request_timeout_seconds=5)

        mod_id, payload = asyncio.run(api.fetch_mod_info_by_source_id("steam", 3701480464))

        self.assertEqual(mod_id, 784)
        self.assertEqual(payload["source"], "steam")
        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "https://api.example/mods")
        self.assertEqual(kwargs["params"]["page_size"], 1)
        self.assertEqual(kwargs["params"]["page"], 0)
        self.assertEqual(kwargs["params"]["sources"], ["steam"])
        self.assertEqual(kwargs["params"]["source_ids"], ["3701480464"])

    def test_fetch_mod_info_by_source_id_supports_factorio_source_ids(self) -> None:
        session = _DummySession(
            {
                ("GET", "https://api.example/mods"): _DummyResponse(
                    status=200,
                    json_payload={
                        "items": [
                            {
                                "id": 107531,
                                "name": "Planet Ribbonia",
                                "size": 1616434,
                                "source": "factorio",
                                "source_id": "ribbonia",
                            }
                        ]
                    },
                )
            }
        )
        api = OpenWorkshopAPI(session, "https://api.example", request_timeout_seconds=5)

        mod_id, payload = asyncio.run(api.fetch_mod_info_by_source_id("factorio", "ribbonia"))

        self.assertEqual(mod_id, 107531)
        self.assertEqual(payload["source"], "factorio")
        method, url, kwargs = session.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(url, "https://api.example/mods")
        self.assertEqual(kwargs["params"]["page_size"], 1)
        self.assertEqual(kwargs["params"]["page"], 0)
        self.assertEqual(kwargs["params"]["sources"], ["factorio"])
        self.assertEqual(kwargs["params"]["source_ids"], ["ribbonia"])

    def test_fetch_download_follows_download_url(self) -> None:
        download_url = "https://storage.example/download/archive/mods/784/main.zip?filename=Wolfein_Race.zip"
        session = _DummySession(
            {
                ("POST", "https://api.example/mods/784/download-url"): _DummyResponse(
                    status=200,
                    json_payload={
                        "download_url": download_url,
                        "filename": "Wolfein_Race.zip",
                    },
                ),
                ("GET", download_url): _DummyResponse(
                    status=200,
                    read_payload=b"zip-bytes",
                    headers={
                        "content-type": "application/zip",
                        "content-disposition": "attachment; filename=Wolfein_Race.zip",
                    },
                ),
            }
        )
        api = OpenWorkshopAPI(session, "https://api.example", request_timeout_seconds=5)

        result = asyncio.run(api.fetch_download(784))

        self.assertEqual(result.kind, "zip")
        self.assertEqual(result.data, b"zip-bytes")
        self.assertEqual(result.filename, "Wolfein_Race.zip")
        self.assertEqual(
            [call[:2] for call in session.calls],
            [
                ("POST", "https://api.example/mods/784/download-url"),
                ("GET", download_url),
            ],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
