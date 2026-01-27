# Photo Keyword Search & Download Service — Windows

Краткая инструкция запуска на Windows (через Docker Desktop + WSL2).

## Требования
- Windows 10/11
- Docker Desktop (WSL2 backend)
- Включён WSL2

## Рекомендации по производительности
- Храните `data/originals` и `data/previews` на SSD.
- Для больших библиотек (300k–400k) лучше размещать проект и данные внутри WSL (например, `/home/<user>/project`) — скан и I/O будут быстрее.
- Не храните библиотеку на сетевых дисках (SMB) — это сильно замедляет `os.walk`.

## Установка (PowerShell)
1) Установите Docker Desktop, включите WSL2 backend.
2) Клонируйте репозиторий.
3) Создайте `.env`:

```powershell
Copy-Item .env.example .env
```

4) Подготовьте папки данных:

```powershell
mkdir data\originals
mkdir data\previews
```

Скопируйте оригиналы в `data\originals`.

## Запуск из WSL (рекомендуется для больших библиотек)
1) Откройте WSL терминал (Ubuntu).
2) Перейдите в домашнюю директорию и клонируйте проект туда:

```bash
git clone <repo> photo-search
cd photo-search
```

3) Создайте `.env`:

```bash
cp .env.example .env
```

4) Подготовьте папки и положите оригиналы:

```bash
mkdir -p data/originals data/previews
```

Если файлы лежат на диске Windows, можно скопировать их в WSL:

```bash
cp -r /mnt/c/Path/To/Originals/* ./data/originals/
```

## Запуск

```powershell
make up
make migrate
make seed-admin
```

Откройте UI: `http://localhost:8080`

## Индексация

```powershell
make rescan
```

## Частые проблемы
- Медленный рескан: разместите проект и данные внутри WSL2.
- Проблемы с доступом к Docker сокету: проверьте, что Docker Desktop запущен и выбран WSL2 backend.
- Ошибка прав на файлы: проверьте, что Docker Desktop имеет доступ к диску (Settings → Resources → File Sharing).
- Долгий старт контейнеров: проверьте, что у Docker выделено достаточно RAM/CPU.

## Проверка сервисов
```powershell
docker compose -f infra/compose/docker-compose.yml ps
```

## Логи
```powershell
docker compose -f infra/compose/docker-compose.yml logs api --tail 200
docker compose -f infra/compose/docker-compose.yml logs worker --tail 200
```

## Остановка

```powershell
make down
```
