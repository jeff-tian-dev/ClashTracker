import logging
import sys
from pathlib import Path

_apps_root = Path(__file__).resolve().parent.parent
if str(_apps_root) not in sys.path:
    sys.path.insert(0, str(_apps_root))

from shared.logutil import configure_logging  # noqa: E402

configure_logging("ingestion")

from .ingest import run_once  # noqa: E402

logger = logging.getLogger("ingestion")


def main() -> None:
    try:
        run_once()
    except Exception:
        logger.exception(
            "Fatal error during ingestion",
            extra={"event": "ingestion.fatal"},
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
