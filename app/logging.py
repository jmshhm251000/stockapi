# app/logging.py
import logging
import sys
from pathlib import Path

def init_logging(level: str = "INFO") -> None:
    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)

    format_ = (
        "%(asctime)s | %(levelname)-8s | "
        "%(name)s:%(lineno)d — %(message)s"
    )

    handlers = [
        logging.FileHandler(log_path / "app.log", mode="a", encoding="utf-8"),
    ]

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=format_,
        handlers=handlers,
    )

    # Silence noisy third-party libraries a bit
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").propagate = True
