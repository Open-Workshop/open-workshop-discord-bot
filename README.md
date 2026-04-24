# Open Workshop - Discord Bot

Discord-бот для скачивания модов Open Workshop напрямую из чата.

## Что изменилось

- Вся кодовая база перенесена в `src/open_workshop_discord_bot/`
- Старые корневые входные файлы удалены
- `config.json` теперь является единственным источником правды для всех несекретных настроек
- Секреты передаются через переменные окружения
- Зависимости теперь лежат в `requirements.txt`

## Установка

1. Скопируйте `.env.example` в `.env`.

```bash
cp .env.example .env
```

2. Укажите `DISCORD_TOKEN` в `.env`.

3. Заполните `config.json` целиком. В коде больше нет запасных значений по умолчанию.
4. Установите зависимости:

```bash
python3 -m pip install -r requirements.txt
```

5. Запустите бота:

```bash
PYTHONPATH=src python3 -m open_workshop_discord_bot
# или
PYTHONPATH=src python3 -m open_workshop_discord_bot --config path/to/config.json
```

## Конфиг

- `config.json` должен содержать все секции и все поля без пропусков
- `discord` - статус, activity и автосинхронизация команд
- `api` - адрес API, сайт, таймаут запроса и порог выдачи прямой ссылки
- `storage` - путь к SQLite-базе, где бот хранит статистику по дням
- `ui` - тексты embed'ов, кнопки и цвета
- `messages` - все пользовательские сообщения и шаблоны
- `commands` - имена и описания slash-команд, а также имя context menu

## Секреты

- `DISCORD_TOKEN` - токен Discord-бота, хранится в `.env`
- `.env` подхватывается автоматически при запуске
