import sys

from app.tasks import extract_metadata_task


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m app.scripts.reextract_metadata <file_id>")
        return
    file_id = sys.argv[1]
    result = extract_metadata_task.delay(file_id)
    print(f"Metadata extraction queued: {result.id}")


if __name__ == "__main__":
    main()
