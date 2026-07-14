from __future__ import annotations

import logging
from pathlib import Path
from datetime import datetime

from core.settings import settings


class ProductionLogger:
    def __init__(self, name: str = "docmorph") -> None:
        self.log_dir = settings.get_log_dir()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
        self.logger.propagate = False
        if not self.logger.handlers:
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
            file_handler = logging.FileHandler(self.log_dir / f"{datetime.utcnow().strftime('%Y-%m-%d')}.log", encoding="utf-8")
            file_handler.setFormatter(formatter)
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            self.logger.addHandler(stream_handler)

    def get_logger(self) -> logging.Logger:
        return self.logger


def get_logger(name: str = "docmorph") -> logging.Logger:
    return ProductionLogger(name).get_logger()
