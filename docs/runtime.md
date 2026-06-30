# Avalone Runtime — что запущено и как переехать на VPS

> Источник истины для развёртывания, мониторинга и аварийного восстановления `avalone.online`.  
> Если вы переносите проект на другой хост — начните с этого файла.

## Общая архитектура

```
┌─────────────────────────────────────────┐
│           Пользователь (браузер)        │
│          открывает https://avalone.online
└──────────────┬──────────────────────────┘
               │ HTTPS (Cloudflare tunnel)
┌──────────────▼──────────────────────────┐
│   cloudflared (online.avalone.tunnel)   │
│   localhost:8811  →  avalone.online     │
└──────────────┬──────────────────────────┘
               │ HTTP
┌──────────────▼──────────────────────────┐
│   online.avalone.landing                │
│   uvicorn + FastAPI, 127.0.0.1:8811     │
│   + SSE /work/events                    │
└──────────────┬──────────────────────────┘
               │ SQLite
┌──────────────▼──────────────────────────┐
│   ~/.avalone/avalone.db                 │
│   (единая БД портала, финансов, работы) │
└──────────────┬──────────────────────────┘
               │
   ┌───────────┴───────────┬─────────────────────────┐
   ▼                       ▼                         ▼
online.avalone.fetch  online.avalone.translate  online.avalone.translate-locations
scripts/fetch_jobs.py   scripts/translate_jobs.py scripts/translate_locations.py
каждые 5 мин            loop, раз в 60 с         loop, раз в 60 с
   ▲                       ▲                        ▲
   └───────────┬───────────┴────────────────────────┘
               │ HTTP/API корейских досок
        Albamon, Saramin, JobKorea,
        114114, Koreabridge

online.avalone.db-backup
infra/backup/backup_db.py
раз в час
```

## Сервисы

| Имя | Роль | Как запускается | Логи | Порт/файлы |
|-----|------|-----------------|------|------------|
| `online.avalone.landing` | Веб-портал | launchd / systemd | `~/Library/Logs/avalone-landing.log` | `127.0.0.1:8811` |
| `online.avalone.fetch` | Парсинг вакансий | launchd `StartInterval=300` / systemd timer | `~/Library/Logs/avalone-fetch.log` | пишет в БД |
| `online.avalone.translate` | Перевод новых постов | launchd `KeepAlive` / systemd service | `~/Library/Logs/avalone-translate.log` | пишет в БД |
| `online.avalone.translate-locations` | Перевод локаций для фильтра | launchd `KeepAlive` / systemd service | `~/Library/Logs/avalone-translate-locations.log` | пишет в БД |
| `online.avalone.db-backup` | Ротация бэкапов БД | launchd `StartInterval=3600` / systemd timer | `~/Library/Logs/db-backup.log` | `~/.avalone/backups/auto` |
| `online.avalone.tunnel` | Cloudflare tunnel | launchd / systemd | `~/Library/Logs/counta-tunnel.log` | `cloudflared` |

## Зависимости

### Системные

- Python 3.13+
- `uv` (https://docs.astral.sh/uv/) — установка зависимостей и запуск
- `git`
- macOS: `launchd` (уже в системе)
- Linux/VPS: `systemd`

### Python-зависимости

Описаны в `pyproject.toml`:

- `fastapi`, `uvicorn[standard]`
- `jinja2`, `pydantic-settings`, `itsdangerous`, `python-multipart`
- `httpx`, `beautifulsoup4`
- `avalone-core`, `avalone-finance` (локальные editable-пакеты из `src/`)

Установка:

```bash
uv sync
```

### Внешние инструменты

- **Kimi CLI** — локальный перевод. Путь: `kimi` или `~/.kimi-code/bin/kimi`. Используется `scripts/translate_jobs.py`.
- **cloudflared** — туннель к Cloudflare. Конфиг: `~/.cloudflared/config.yml` (не в git).

## Пути данных

| Путь | Назначение | Нужно бэкапить |
|------|------------|----------------|
| `~/.avalone/avalone.db` | Основная SQLite БД | ✅ |
| `~/.avalone/backups/auto` | Автобэкапы БД | ✅ (резерв) |
| `~/Library/Logs/avalone-*.log` | Логи сервисов | опционально |
| `~/.cloudflared/config.yml` | Конфиг туннеля | ✅ |
| `~/.avalone/avalone.db` | Финансовая БД (legacy, сейчас в `avalone.db`) | ✅ |

## Переменные окружения

Задаются в launchd plist / systemd unit / `.env`.

| Переменная | Где используется | Пример | Комментарий |
|------------|------------------|--------|-------------|
| `AVALONE_FERNET_KEY` | Шифрование сессий | `fMsSHaKIt2QKZxt7rYc_GO8ODb-1Zrcfgo3HUFB6tI8=` | Сменить в продакшене |
| `AVALONE_ADMIN_EMAIL` | Уведомления | `prontost@gmail.com` | |
| `AVALONE_WEB_PORT` | Порт веб-сервера | `8811` | |
| `AVALONE_DB_PATH` | Путь к БД | `~/.avalone/avalone.db` | опционально, есть дефолт |
| `PATH` | Поиск бинарников | `/usr/local/bin:/usr/bin:/bin` | должен включать `kimi` и `cloudflared` |

**Важно:** секреты не хранятся в git. Локально они прописаны в `~/Library/LaunchAgents/online.avalone.landing.plist`. На VPS — в systemd unit или в `.env` с правами `600`.

## Управление сервисами на macOS

```bash
# Список
launchctl list | grep online.avalone

# Перезапуск веб-сервера
launchctl bootout gui/$(id - u)/online.avalone.landing
launchctl bootstrap gui/$(id - u) ~/Library/LaunchAgents/online.avalone.landing.plist

# Перезапуск fetch
launchctl bootout gui/$(id - u)/online.avalone.fetch 2>/dev/null || true
launchctl bootstrap gui/$(id - u) infra/launchd/online.avalone.fetch.plist

# Перезапуск translate
launchctl bootout gui/$(id - u)/online.avalone.translate 2>/dev/null || true
launchctl bootstrap gui/$(id - u) infra/launchd/online.avalone.translate.plist
```

## Перенос на VPS (Ubuntu + systemd)

### 1. Подготовка сервера

```bash
# От имени пользователя avalone (или другого не-root)
sudo apt update
sudo apt install -y python3.13 python3.13-venv python3-pip git curl

# Установка uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

### 2. Клонирование и зависимости

```bash
git clone https://github.com/prontost/avalone.online.git ~/avalone.online
cd ~/avalone.online
uv sync
```

### 3. Перенос данных

```bash
# На старом хосте:
scp ~/.avalone/avalone.db user@vps:/home/user/.avalone/avalone.db

# На VPS:
mkdir -p ~/.avalone/backups/auto
```

### 4. systemd unit — веб-сервер

Создать `/etc/systemd/system/avalone-landing.service`:

```ini
[Unit]
Description=Avalone landing portal
After=network.target

[Service]
Type=simple
User=avalone
Group=avalone
WorkingDirectory=/home/avalone/avalone.online
ExecStart=/home/avalone/avalone.online/.venv/bin/python -m uvicorn avalone_landing.web.app:app --host 127.0.0.1 --port 8811
Restart=always
RestartSec=5
Environment="PATH=/home/avalone/.local/bin:/usr/local/bin:/usr/bin:/bin"
Environment="AVALONE_FERNET_KEY=change-me-in-production"
Environment="AVALONE_ADMIN_EMAIL=admin@avalone.online"
Environment="AVALONE_WEB_PORT=8811"

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now avalone-landing
```

### 5. systemd timer — fetch

`/etc/systemd/system/avalone-fetch.service`:

```ini
[Unit]
Description=Avalone job fetcher

[Service]
Type=oneshot
User=avalone
Group=avalone
WorkingDirectory=/home/avalone/avalone.online
ExecStart=/home/avalone/avalone.online/.venv/bin/python scripts/fetch_jobs.py --days 14
Environment="PATH=/home/avalone/.local/bin:/usr/local/bin:/usr/bin:/bin"
```

`/etc/systemd/system/avalone-fetch.timer`:

```ini
[Unit]
Description=Run Avalone fetch every 5 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now avalone-fetch.timer
```

### 6. systemd service — translate

`/etc/systemd/system/avalone-translate.service`:

```ini
[Unit]
Description=Avalone translator loop
After=network.target

[Service]
Type=simple
User=avalone
Group=avalone
WorkingDirectory=/home/avalone/avalone.online
ExecStart=/home/avalone/avalone.online/.venv/bin/python scripts/translate_jobs.py --source ko --lang ru --loop --interval 60 --max-failures 10
Restart=always
RestartSec=10
Environment="PATH=/home/avalone/.local/bin:/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now avalone-translate
```

### 7. systemd service — translate-locations

`/etc/systemd/system/avalone-translate-locations.service`:

```ini
[Unit]
Description=Avalone location translator loop
After=network.target

[Service]
Type=simple
User=avalone
Group=avalone
WorkingDirectory=/home/avalone/avalone.online
ExecStart=/home/avalone/avalone.online/.venv/bin/python scripts/translate_locations.py --batch 5 --loop --interval 60 --max-failures 10
Restart=always
RestartSec=10
Environment="PATH=/home/avalone/.local/bin:/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now avalone-translate-locations
```

### 8. systemd timer — backup

`/etc/systemd/system/avalone-backup.service`:

```ini
[Unit]
Description=Avalone DB backup

[Service]
Type=oneshot
User=avalone
Group=avalone
WorkingDirectory=/home/avalone/avalone.online
ExecStart=/home/avalone/avalone.online/.venv/bin/python infra/backup/backup_db.py --config infra/backup/backup-config.json --retention-days 14
```

`/etc/systemd/system/avalone-backup.timer`:

```ini
[Unit]
Description=Backup Avalone DB every hour

[Timer]
OnBootSec=5min
OnUnitActiveSec=1h

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now avalone-backup.timer
```

### 9. Публикация наружу

Вариант A — Cloudflare tunnel (как сейчас):

```bash
# Установить cloudflared
# Скопировать ~/.cloudflared/config.yml со старого хоста
cloudflared tunnel --config ~/.cloudflared/config.yml run
```

Вариант B — Nginx reverse proxy:

```nginx
server {
    listen 443 ssl http2;
    server_name avalone.online;

    location / {
        proxy_pass http://127.0.0.1:8811;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support
        proxy_buffering off;
        proxy_read_timeout 86400;
    }
}
```

## Smoke-тесты после переезда

```bash
# 1. Сервисы запущены
sudo systemctl status avalone-landing
sudo systemctl status avalone-translate
systemctl list-timers | grep avalone

# 2. Локальный healthcheck
curl -fsS http://127.0.0.1:8811/healthz

# 3. Внешний healthcheck
curl -fsS https://avalone.online/healthz

# 4. SSE работает
curl -N http://127.0.0.1:8811/work/events

# 5. Перевод не падает
journalctl -u avalone-translate -f

# 6. Перевод локаций не падает
journalctl -u avalone-translate-locations -f

# 7. Fetch не падает
journalctl -u avalone-fetch -f

# 8. Бэкапы создаются
ls -la ~/.avalone/backups/auto
```

## Частые проблемы

### Too many open files

Причина была в утечке SQLite-соединений. Исправлено через `ClosingConnection` в `avalone_core/database.py`. Если повторится — проверить `lsof -p <pid> | wc -l`.

### Перевод остановился

Смотреть `~/Library/Logs/avalone-translate.log` или `journalctl -u avalone-translate`. Возможные причины: Kimi CLI недоступен, исчерпан лимит, сеть.

### Перевод локаций остановился

Смотреть `~/Library/Logs/avalone-translate-locations.log` или `journalctl -u avalone-translate-locations`. Таблица `work_location_translations` должна постепенно заполняться уникальными локациями.

### Fetch не приносит новые посты

Смотреть лог `avalone-fetch.log`. Возможно, источник изменил вёрстку или API.

## Чеклист резервного копирования перед любыми манипуляциями

- [ ] `~/.avalone/avalone.db` скопирована.
- [ ] `~/.cloudflared/config.yml` скопирован.
- [ ] launchd plist / systemd unit сохранены.
- [ ] Изменения закоммичены и запушены в git.
