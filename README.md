# Stats Tracker Bot

Telegram бот для автоматической отправки статистики из admin.doxmediagroup.com два раза в сутки.

## Функции

- Автоматическая отправка статистики в 00:00 и 12:00 (по Москве)
- Разделение статистики на два блока: **p2pDox** и **Doxposting**
- HTML форматирование сообщений (заголовки жирным)
- Команды для ручного получения статистики

## Команды бота

- `/start` - Показать информацию о боте и Chat ID
- `/chatid` - Получить Chat ID текущего чата
- `/stats` - Получить статистику немедленно

## Настройка

### Переменные окружения

Создайте файл `.env` или установите переменные окружения на Railway:

```
TELEGRAM_BOT_TOKEN=ваш_токен_бота
TELEGRAM_CHAT_ID=id_группы_или_чата
STATS_LOGIN=логин_от_сайта
STATS_PASSWORD=пароль_от_сайта
SCHEDULE_HOURS=0,12
TIMEZONE=Europe/Moscow
SELENIUM_HEADLESS=true
```

### Получение Chat ID

1. Добавьте бота в группу
2. Отправьте команду `/chatid` в группе
3. Скопируйте полученный Chat ID
4. Добавьте его в переменную `TELEGRAM_CHAT_ID`

## Деплой на Railway

### Способ 1: Через GitHub

1. Загрузите код в GitHub репозиторий
2. Создайте новый проект на Railway
3. Подключите GitHub репозиторий
4. Добавьте переменные окружения в настройках проекта
5. Railway автоматически задеплоит проект

### Способ 2: Через Railway CLI

```bash
railway login
railway init
railway up
```

Затем добавьте переменные окружения через Dashboard или CLI:

```bash
railway variables set TELEGRAM_BOT_TOKEN=ваш_токен
railway variables set TELEGRAM_CHAT_ID=ваш_chat_id
railway variables set STATS_LOGIN=ваш_логин
railway variables set STATS_PASSWORD=ваш_пароль
```

## Формат сообщений

```
p2pDox
Количество пользователей за все время: 2861
Активных пользователей: 58
Среднее количество действий: 1,83

Doxposting
Пользователей всего: 213
Активных пользователей: 29
Бот добавлен как админ в каналов всего: 138

Посты
Опубликовано: 2372
Отложено: 151
С ошибками: 25

Сторис
Опубликовано: 19
Отложено: 0
С ошибками: 1
```

## Локальный запуск

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск
python main.py
```

## Файловая структура

```
├── main.py           # Основной файл бота
├── scraper.py        # Модуль парсинга статистики
├── config.py         # Конфигурация
├── requirements.txt  # Зависимости Python
├── Dockerfile        # Docker образ с Chrome
├── Procfile          # Конфигурация Railway
├── railway.json      # Настройки Railway
└── env.example       # Пример переменных окружения
```
