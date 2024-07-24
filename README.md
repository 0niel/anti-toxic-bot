# AntiToxicBot 🤖🚫

AntiToxicBot — это Telegram-бот, который борется с токсичностью в чатах. Он использует Perspective API для анализа сообщений и выдает муты за токсичное поведение.

## Установка и настройка 🛠️

### С использованием Poetry

1. Клонируйте репозиторий:
    ```bash
    git clone https://github.com/yourusername/AntiToxicBot.git
    ```
2. Перейдите в директорию проекта:
    ```bash
    cd AntiToxicBot
    ```
3. Установите зависимости:
    ```bash
    poetry install
    ```
4. Создайте файл `.env` и добавьте ваши ключи API:
    ```env
    PERSPECTIVE_API_KEY=your_perspective_api_key
    TELEGRAM_BOT_TOKEN=your_telegram_bot_token
    ```

### С использованием Docker

1. Клонируйте репозиторий:
    ```bash
    git clone https://github.com/0niel/anti-toxic-bot.git
    ```
2. Перейдите в директорию проекта:
    ```bash
    cd anti-toxic-bot
    ```
3. Соберите Docker-образ:
    ```bash
    docker build -t tg-bot .
    ```
4. Создайте файл `.env` и добавьте ваши ключи API:
    ```env
    PERSPECTIVE_API_KEY=your_perspective_api_key
    TELEGRAM_BOT_TOKEN=your_telegram_bot_token
    ```
5. Запустите контейнер:
    ```bash
    docker run --env-file .env -p 5000:5000 --name tg-bot tg-bot
    ```

## Запуск 🚀

### С использованием Poetry

1. Запустите бота:
    ```bash
    poetry run python main.py
    ```

### С использованием Docker

1. Запустите контейнер:
    ```bash
    docker run --env-file .env -p 5000:5000 --name tg-bot tg-bot
    ```

## Команды 📋

- `/start` — приветственное сообщение.
- `/muted_users` — получить список замученных пользователей.

## Makefile команды 🛠️

- `make format` — Запуск инструментов форматирования кода.
- `make build` — Сборка Docker-образа.
- `make run` — Запуск Docker-контейнера.
- `make stop` — Остановка и удаление Docker-контейнера.
- `make restart` — Остановка, пересборка и запуск Docker-контейнера.
- `make clean` — Удаление Docker-образа.
- `make logs` — Показ логов работающего контейнера.
- `make shell` — Открытие шелла внутри работающего контейнера.
- `make prune` — Удаление всех неиспользуемых объектов Docker.

## Лицензия 📜

Этот проект лицензируется на условиях лицензии MIT.
