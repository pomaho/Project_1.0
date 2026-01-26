from app.tasks import scan_storage_task


def main() -> None:
    result = scan_storage_task.delay()
    print(f"Rescan queued: {result.id}")


if __name__ == "__main__":
    main()
