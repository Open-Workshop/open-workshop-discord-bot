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

## Добавление на сервер

Чтобы bot user появился участником сервера и был виден в `Guilds` при запуске,
приложение нужно установить с OAuth2 scope `bot`. Одного `applications.commands`
недостаточно: так Discord может добавить slash-команды, но не добавить самого
бота как участника сервера.

В Discord Developer Portal:

1. Откройте `Installation`.
2. Для `Guild Install` включите scopes `bot` и `applications.commands`.
3. В bot permissions выберите минимум `View Channels`, `Send Messages`,
   `Embed Links` и `Attach Files`.
4. Используйте Guild Install / OAuth2 URL Generator, а не User Install.

Прямая форма ссылки:

```text
https://discord.com/oauth2/authorize?client_id=<APPLICATION_ID>&scope=bot%20applications.commands&permissions=52224
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
