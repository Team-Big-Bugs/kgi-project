from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal
from app.services.scheduler import run_scheduler


def main() -> None:
    with SessionLocal() as db:
        stats = run_scheduler(db)
    print(stats)


if __name__ == "__main__":
    main()
