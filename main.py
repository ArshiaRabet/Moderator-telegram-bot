"""Entry point for running the Telegram group management bot."""
import logging
import sys

from group_bot.bot import run_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)


if __name__ == "__main__":
    run_bot()
