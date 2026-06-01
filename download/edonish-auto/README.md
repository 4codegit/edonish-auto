# eDonish Auto 📚

**Автоматизация электронного журнала edonish.tj**

Десктопная программа для автоматического заполнения оценок в электронном журнале eDonish (г. Душанбе, Таджикистан).

## Возможности

- 🔐 **Автоматический вход** — логин через API, получение всех данных (школа, классы, предметы, четверти)
- 📋 **Автоматический анализ** — программа сама находит все классы, предметы, четверти, даты и студентов
- 🎯 **Авто-оценки** — заполнение оценок (8-10) на все пустые ячейки журнала
- ⚡ **Параллельные воркеры** — многопоточная обработка (4+ воркеров одновременно)
- 📊 **Просмотр журнала** — удобный просмотр оценок по классам/предметам/четвертям
- 🔄 **Четвертные оценки** — автоматическое заполнение четвертных, семестровых и годовых оценок
- 📝 **Логирование** — подробные логи всех операций
- 🐳 **Docker** — запуск в контейнере (CLI и GUI режимы)

## Быстрый старт

### Способ 1: Docker (рекомендуется)

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/YOUR_USERNAME/edonish-auto.git
cd edonish-auto

# 2. Создайте .env файл с вашими данными
cp .env.example .env
# Отредактируйте .env: впишите логин и пароль

# 3. Запустите CLI (headless, без GUI)
docker compose up

# Или с явными параметрами
docker compose run edonish-cli --login 200117707 --password test123 --class "8Б"
```

### Способ 2: Docker — GUI режим (только Linux с X11)

```bash
# Разрешите X11 подключения
xhost +local:docker

# Запустите GUI
docker compose --profile gui up edonish-gui

# После завершения
xhost -local:docker
```

### Способ 3: Установка вручную (Python)

```bash
# Linux/Mac
chmod +x run.sh
./run.sh

# Или вручную
pip install customtkinter requests
python3 main.py
```

### Способ 4: CLI режим (без GUI)

```bash
pip install customtkinter requests

# Заполнить все пустые оценки
python3 main_cli.py --login 200117707 --password test123

# Только для конкретного класса/предмета/четверти
python3 main_cli.py --login 200117707 --password test123 \
  --class "8Б" --subject "Технологияи иттилоотӣ" --quarter "Чоряки 4"

# Только анализ (без записи)
python3 main_cli.py --login 200117707 --password test123 --analyze-only

# Просмотр журнала
python3 main_cli.py --login 200117707 --password test123 \
  --view-journal --class "8Б" --subject "Технологияи иттилоотӣ" --quarter "Чоряки 4"

# С сохранением отчёта в JSON
python3 main_cli.py --login 200117707 --password test123 --save-report --json-output
```

## Docker: подробности

### CLI режим (по умолчанию)

Работает без GUI, идеально для серверов и CI/CD:

```bash
# Сборка
docker compose build

# Запуск с переменными из .env
docker compose up

# Запуск с аргументами командной строки
docker compose run edonish-cli --login 200117707 --password test123 --min-grade 9 --max-grade 10

# Только анализ
docker compose run edonish-cli --login 200117707 --password test123 --analyze-only --save-report
```

### Переменные окружения (для Docker)

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `EDONISH_LOGIN` | Логин от edonish.tj | — |
| `EDONISH_PASSWORD` | Пароль от edonish.tj | — |
| `EDONISH_MIN_GRADE` | Минимальная оценка | 8 |
| `EDONISH_MAX_GRADE` | Максимальная оценка | 10 |
| `EDONISH_WORKERS` | Количество параллельных воркеров | 4 |
| `EDONISH_CLASS` | Фильтр по классу | all |
| `EDONISH_SUBJECT` | Фильтр по предмету | all |
| `EDONISH_QUARTER` | Фильтр по четверти | all |
| `EDONISH_FILL_EMPTY` | Только пустые ячейки | true |
| `EDONISH_QUARTER_MARKS` | Четвертные оценки | true |

### Volumes

| Путь | Описание |
|------|----------|
| `./logs` | Логи выполнения |
| `./output` | Отчёты в JSON |

## CLI параметры

```
python3 main_cli.py [OPTIONS]

Обязательные:
  --login LOGIN         Логин (ID) от edonish.tj
  --password PASSWORD   Пароль от edonish.tj

Фильтры:
  --class CLASS         Класс (напр. '8Б') или 'all' (default: all)
  --subject SUBJECT     Предмет или 'all' (default: all)
  --quarter QUARTER     Четверть или 'all' (default: all)

Оценки:
  --min-grade N         Минимальная оценка (default: 8)
  --max-grade N         Максимальная оценка (default: 10)

Выполнение:
  --workers N           Количество воркеров (default: 4)
  --fill-empty BOOL     Только пустые ячейки (default: True)
  --quarter-marks BOOL  Четвертные оценки (default: True)
  --analyze-only        Только анализ, без записи
  --view-journal        Просмотр журнала

Вывод:
  --json-output         Результат в JSON
  --save-report         Сохранить отчёт в файл
```

## Структура проекта

```
edonish-auto/
├── main.py              # GUI приложение (CustomTkinter)
├── main_cli.py          # CLI интерфейс (headless, для Docker)
├── api_client.py        # API клиент edonish.tj
├── grade_engine.py      # Движок автоматизации оценок
├── config.py            # Конфигурация
├── requirements.txt     # Зависимости Python
├── Dockerfile           # Docker сборка (multi-stage)
├── docker-compose.yml   # Docker Compose
├── .dockerignore        # Исключения для Docker
├── .gitignore           # Исключения для Git
├── .env.example         # Пример переменных окружения
├── run.sh               # Скрипт запуска (Linux/Mac)
└── README.md            # Документация
```

## API Endpoints (обнаружено)

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/auth/v1/login` | POST | Авторизация |
| `/auth/v1/refresh_token` | GET | Обновление токена |
| `/auth/v1/header/info` | GET | Информация о пользователе |
| `/teacher/v1/journal` | OPTIONS | Доступные классы/предметы |
| `/teacher/v1/journal/dates` | GET | Даты журнала |
| `/teacher/v1/journal/students` | GET | Студенты с оценками |
| `/teacher/v1/journal/10_point_mark/create` | POST | Создание оценки |
| `/teacher/v1/journal/10_point_quarter_mark/create` | POST | Четвертная оценка |
| `/teacher/v1/journal/10_point_semester/create` | POST | Семестровая оценка |
| `/teacher/v1/journal/10_point_year/create` | POST | Годовая оценка |
| `/teacher/v1/journal/mark/delete` | POST | Удаление оценки |
| `/school_admin/v1/period/quaters` | GET | Список четвертей |
| `/groups/list` | GET | Список классов школы |
| `/teacher/subject` | GET | Предметы учителя |
| `/subgroups` | GET | Подгруппы класса |

## Поддерживаемые роли

| Роль | Префикс API |
|------|-------------|
| teacher | /teacher/v1 |
| classroom-teacher | /teacher/v1 |
| school_admin | /school_admin/v1 |
| director | /director/v1 |
| headteacher | /headteacher/v1 |
| parent | /parent/v1 |
| student | /student/v1 |

## Безопасность

- Токены JWT хранятся только в памяти
- Пароли не сохраняются
- Все запросы идут через HTTPS
- `.env` файлы исключены из Git

## Требования

- Python 3.8+ (или Docker)
- Интернет-соединение
- Для GUI режима: X11 (Linux) или нативный дисплей
