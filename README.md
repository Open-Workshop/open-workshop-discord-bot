# Open Workshop - Discord Bot

Discord-бот для скачивания модов Open Workshop напрямую из чата.

## Что изменилось

- Вся кодовая база перенесена в `src/open_workshop_discord_bot/`
- Старые корневые входные файлы удалены
- Конфигурация больше не завязана на `key.json`
- Зависимости теперь лежат в `requirements.txt`

## Установка

1. Скопируйте `.env.example` в `.env` или задайте переменные окружения вручную.
2. Укажите `DISCORD_TOKEN`.
3. Установите зависимости:

```bash
python3 -m pip install -r requirements.txt
```

4. Запустите бота:

```bash
PYTHONPATH=src python3 -m open_workshop_discord_bot
```

## Переменные окружения

- `DISCORD_TOKEN` - токен Discord-бота, обязателен
- `OPENWORKSHOP_API_URL` - базовый URL API, по умолчанию `https://api.openworkshop.su`
- `OPENWORKSHOP_WEBSITE_URL` - базовый URL сайта, по умолчанию `https://openworkshop.su`
- `OPENWORKSHOP_DIRECT_DOWNLOAD_THRESHOLD_BYTES` - порог, после которого бот дает прямую ссылку вместо файла
- `OPENWORKSHOP_REQUEST_TIMEOUT_SECONDS` - таймаут обычных запросов к API
- `OPENWORKSHOP_STATISTICS_TIMEOUT_SECONDS` - таймаут запроса статистики
