from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from .bot import WorkshopBot
from .config import BotConfig, CONFIG_PATH, ConfigurationError


LOGGER = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="open-workshop-bot",
        description="Open Workshop Discord bot",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=str(CONFIG_PATH),
        help="Path to config.json",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    dotenv_path = Path(args.config).with_name(".env")
    if not dotenv_path.exists():
        found_dotenv = find_dotenv(usecwd=True)
        if found_dotenv:
            dotenv_path = Path(found_dotenv)
    if dotenv_path.exists():
        load_dotenv(dotenv_path)

    try:
        config = BotConfig.from_file(args.config)
    except ConfigurationError as exc:
        LOGGER.error("%s", exc)
        return 2

    bot = WorkshopBot(config)
    bot.run(config.discord_token, log_handler=None)
    return 0
