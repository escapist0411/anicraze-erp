import logging
import logging.config

from app.config.settings import get_settings


def configure_logging() -> None:
    settings = get_settings()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"standard": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
            "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "standard"}},
            "root": {"handlers": ["console"], "level": settings.log_level.upper()},
        }
    )
