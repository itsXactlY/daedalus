"""
AccessLogger JSONL with log rotation.
- 100MB per file
- Max 5 rotated files
- 30-day cleanup of old logs
"""

import json
import logging
import os
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler


class AccessLogger:
    LOG_DIR = "/var/log/daedalus"
    MAX_BYTES = 100 * 1024 * 1024  # 100MB
    BACKUP_COUNT = 5
    RETENTION_DAYS = 30

    def __init__(self, log_file: str = "access.jsonl"):
        self.log_path = os.path.join(self.LOG_DIR, log_file)
        os.makedirs(self.LOG_DIR, exist_ok=True)

        self.logger = logging.getLogger("AccessLogger")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        if not self.logger.handlers:
            handler = RotatingFileHandler(
                self.log_path,
                maxBytes=self.MAX_BYTES,
                backupCount=self.BACKUP_COUNT,
                encoding="utf-8",
            )
            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self._cleanup_old_logs()

    def _cleanup_old_logs(self):
        """Remove log files older than RETENTION_DAYS."""
        cutoff = time.time() - (self.RETENTION_DAYS * 86400)
        base = self.log_path
        for i in range(self.BACKUP_COUNT + 1):
            f = f"{base}.{i}" if i > 0 else base
            if os.path.exists(f):
                if os.path.getmtime(f) < cutoff:
                    try:
                        os.remove(f)
                    except OSError:
                        pass

    def log(self, query_embedding: list[float], result_ids: list[int],
            result_scores: list[float], timestamp=None):
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat() + "Z"
        entry = {
            "timestamp": timestamp,
            "query_embedding": query_embedding,
            "result_ids": result_ids,
            "result_scores": result_scores,
        }
        self.logger.info(json.dumps(entry))


if __name__ == "__main__":
    logger = AccessLogger()
    logger.log(
        query_embedding=[0.1] * 128,
        result_ids=[1, 2, 3],
        result_scores=[0.9, 0.8, 0.7],
    )
    print("AccessLogger with rotation initialized.")
