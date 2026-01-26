from app.tasks import queue_missing_previews_task


def main() -> None:
    result = queue_missing_previews_task.delay()
    print(f"Rebuild previews queued: {result.id}")


if __name__ == "__main__":
    main()
