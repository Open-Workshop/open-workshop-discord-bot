from __future__ import annotations

import os
import pathlib
import sys
import unittest
from unittest.mock import patch

import aiohttp


ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from open_workshop_discord_bot.config import BotConfig
from open_workshop_discord_bot.health import HealthProbeServer


class HealthProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_healthz_and_readyz(self) -> None:
        probe = HealthProbeServer(host="127.0.0.1", port=0)

        await probe.start()
        try:
            self.assertTrue(probe.addresses)
            host, port = probe.addresses[0]
            base_url = f"http://{host}:{port}"

            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base_url}/healthz") as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(await response.json(), {"status": "ok"})

                async with session.get(f"{base_url}/readyz") as response:
                    self.assertEqual(response.status, 503)
                    self.assertEqual(
                        await response.json(),
                        {"status": "starting", "ready": False},
                    )

                probe.mark_ready()

                async with session.get(f"{base_url}/readyz") as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(
                        await response.json(),
                        {"status": "ok", "ready": True},
                    )
        finally:
            await probe.stop()


class BotConfigHealthTests(unittest.TestCase):
    def test_bot_config_defaults_health_section(self) -> None:
        payload = {
            "discord": {
                "status": "online",
                "sync_commands_on_startup": False,
                "activity": {
                    "type": "playing",
                    "name": "test",
                },
            },
            "api": {
                "base_url": "https://api.example",
                "website_url": "https://site.example",
                "direct_download_threshold_bytes": 1,
                "request_timeout_seconds": 1.0,
            },
            "storage": {
                "database_path": "data/statistics.sqlite3",
            },
            "ui": {
                "statistics_embed_title": "stats",
                "statistics_embed_color": "blurple",
                "project_embed_title": "project",
                "project_embed_color": "blurple",
                "large_mod_embed_color": "blurple",
                "direct_download_button_label": "Download",
                "website_button_label": "Site",
                "project_buttons": [
                    {"label": "GitHub", "emoji": None, "url": "https://github.com"},
                ],
            },
            "messages": {
                "server_unavailable": "offline",
                "invalid_link": "invalid",
                "need_specific_mod_link": "specific",
                "unsupported_source": "unsupported",
                "download_prompt": "prompt",
                "negative_mod_id": "negative",
                "download_started": "started",
                "download_duration_template": "{elapsed}",
                "large_mod_title_template": "{name}",
                "large_mod_description": "desc",
                "mod_not_found": "missing",
                "unexpected_response": "unexpected",
            },
            "commands": {
                "statistics": {"name": "stats", "description": "stats"},
                "project": {"name": "project", "description": "project"},
                "download": {"name": "download", "description": "download"},
                "context_menu_name": "Download mod",
            },
        }

        with patch.dict(os.environ, {"DISCORD_TOKEN": "token-for-tests"}, clear=False):
            config = BotConfig.from_mapping(payload)

        self.assertEqual(config.health.host, "0.0.0.0")
        self.assertEqual(config.health.port, 8089)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
