COMPOSE_FILE=infra/compose/docker-compose.yml

.PHONY: up down migrate seed-admin rescan gc-previews rebuild-previews reextract-metadata

up:
	docker compose -f $(COMPOSE_FILE) up -d --build

down:
	docker compose -f $(COMPOSE_FILE) down

migrate:
	docker compose -f $(COMPOSE_FILE) run --rm api alembic upgrade head

seed-admin:
	docker compose -f $(COMPOSE_FILE) run --rm api python -m app.scripts.seed_admin

rescan:
	docker compose -f $(COMPOSE_FILE) run --rm api python -m app.scripts.rescan

gc-previews:
	docker compose -f $(COMPOSE_FILE) run --rm api python -m app.scripts.gc_previews

rebuild-previews:
	docker compose -f $(COMPOSE_FILE) run --rm api python -m app.scripts.rebuild_previews

reextract-metadata:
	docker compose -f $(COMPOSE_FILE) run --rm api python -m app.scripts.reextract_metadata $(FILE_ID)
