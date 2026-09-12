"""Structured logging for the harmonization engine.

Replaces scattered ``print`` statements with Python logging. Every record
carries a ``job_id`` (bound via contextlib) so results from different
pipeline runs can be traced in a shared log file.
"""

from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path

job_id_var: ContextVar[str] = ContextVar("harmonizer_job_id", default="cli")

_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] job=%(job_id)s %(message)s"
_DATE_FMT = "%Y-%m-%dT%H:%M:%S"


class JobIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.job_id = job_id_var.get() or "-"
        return True


@contextmanager
def job_context(job_id: str):
    """Bind a pipeline job id to every log record emitted in this scope."""
    token = job_id_var.set(job_id)
    try:
        yield
    finally:
        job_id_var.reset(token)


def setup_logging(log_dir: Path | None = None, level: str = "INFO") -> None:
    """Configure the root logger with a console handler and an optional
    rotating file handler."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FMT)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.addFilter(JobIdFilter())
    root.addHandler(console)

    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "harmonizer.log",
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(JobIdFilter())
        root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)