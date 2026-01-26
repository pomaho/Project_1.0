from app.tasks import gc_previews_task


def main() -> None:
    result = gc_previews_task.delay()
    print(f"GC previews queued: {result.id}")


if __name__ == "__main__":
    main()
