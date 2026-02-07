from app.tasks import cleanup_orphan_previews_task

if __name__ == '__main__':
    result = cleanup_orphan_previews_task.delay()
    print(f'Cleanup orphan previews queued: {result.id}')
