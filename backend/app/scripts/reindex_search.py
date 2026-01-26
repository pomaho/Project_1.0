from app import models
from app.db import SessionLocal
from app.search_index import upsert_file


def main() -> None:
    session = SessionLocal()
    try:
        ids = [row.id for row in session.query(models.File.id).filter(models.File.deleted_at.is_(None))]
        for file_id in ids:
            upsert_file(session, file_id)
        print(f"Reindex requested for {len(ids)} files")
    finally:
        session.close()


if __name__ == "__main__":
    main()
