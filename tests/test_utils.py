from __future__ import annotations

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

from open_workshop_discord_bot.utils import parse_workshop_reference


class WorkshopReferenceParsingTests(unittest.TestCase):
    def test_parse_openworkshop_api_link(self) -> None:
        reference = parse_workshop_reference("https://api.openworkshop.miskler.ru/mods/69752")

        self.assertIsNotNone(reference)
        assert reference is not None
        self.assertEqual(reference.id, 69752)
        self.assertEqual(reference.kind, "openworkshop")

    def test_parse_openworkshop_link_on_any_host(self) -> None:
        reference = parse_workshop_reference("https://example.com/mod/69752?game=5")

        self.assertIsNotNone(reference)
        assert reference is not None
        self.assertEqual(reference.id, 69752)
        self.assertEqual(reference.kind, "openworkshop")

    def test_parse_factorio_mod_link(self) -> None:
        reference = parse_workshop_reference("https://mods.factorio.com/mod/Teleportation_Redux")

        self.assertIsNotNone(reference)
        assert reference is not None
        self.assertEqual(reference.id, "Teleportation_Redux")
        self.assertEqual(reference.kind, "factorio")

    def test_parse_factorio_mods_path_link(self) -> None:
        reference = parse_workshop_reference("https://mods.factorio.com/mods/Apriori/Teleportation")

        self.assertIsNotNone(reference)
        assert reference is not None
        self.assertEqual(reference.id, "Teleportation")
        self.assertEqual(reference.kind, "factorio")

    def test_parse_factorio_raw_slug(self) -> None:
        reference = parse_workshop_reference("ribbonia")

        self.assertIsNotNone(reference)
        assert reference is not None
        self.assertEqual(reference.id, "ribbonia")
        self.assertEqual(reference.kind, "factorio")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
