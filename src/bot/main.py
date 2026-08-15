"""Entry point: python -m bot.main"""

from __future__ import annotations

from bot.config import load_config
from bot.logger import setup_logging
from bot.runner import run


def main() -> None:
    setup_logging()
    cfg = load_config()
    run(cfg)


if __name__ == "__main__":
    main()
