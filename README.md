# Photo Keyword Search & Download Service

Self-hosted сервис для индексации фото, извлечения ключевых слов, генерации превью и поиска с продвинутыми операторами.

## Структура монорепозитория
- `backend/` FastAPI + Celery + Postgres + Meilisearch
- `frontend/` React (TypeScript) + Vite + MUI
- `infra/` Docker Compose и конфиги reverse proxy
- `docs/` ADR и заметки

## Быстрый старт (dev)
1) Скопируйте `.env.example` в `.env` и настройте значения
2) Запустите сервисы:

```bash
make up
```

3) Примените миграции:

```bash
make migrate
```

4) Создайте админа:

```bash
make seed-admin
```

5) Откройте UI через прокси: `http://localhost:8080`

## Данные для файлового режима
- Оригиналы: `./data/originals` (монтируется как `/data/originals`, read-only)
- Превью: `./data/previews` (монтируется как `/data/previews`)

## Индексация
- Первичный скан:

```bash
make rescan
```

- Полный реиндекс поиска:

```bash
docker compose -f infra/compose/docker-compose.yml exec api python -m app.scripts.reindex_search
```

- Очистка превью удалённых файлов:

```bash
make gc-previews
```

- Пересбор превью для файлов без превью:

```bash
make rebuild-previews
```

## Сервисы
- API: `http://localhost:8000`
- Meilisearch: `http://localhost:7700`
- Консоль MinIO: `http://localhost:9001` (опционально)
- Прокси: `http://localhost:8080`

## Миграции
Alembic настроен в `backend/migrations`. Для применения используйте `make migrate`.

## Документация
- ADR: `docs/ADR-001-meilisearch.md`

## Примечания
Это базовый каркас для этапов M1-M2. Ключевые части (парсер запросов, задачи индексации, ACL) пока в виде заглушек и будут реализованы итеративно.

## Ограничение скачивания
Лимит скачиваний на пользователя в минуту задаётся через `RATE_LIMIT_DOWNLOADS_PER_MIN` в `.env`.
