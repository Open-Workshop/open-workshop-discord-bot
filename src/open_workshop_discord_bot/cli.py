from __future__ import annotations

import logging

from dotenv import load_dotenv

from .bot import WorkshopBot
from .config import ConfigurationError, Settings


LOGGER = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    load_dotenv()

    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        LOGGER.error("%s", exc)
        return 2

    bot = WorkshopBot(settings)
    bot.run(settings.discord_token, log_handler=None)
    return 0
