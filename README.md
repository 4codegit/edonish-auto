# Edonish Auto - Go/Fyne версия 📚

**Автоматизация электронного журнала edonish.tj на Go с Fyne GUI**

Десктопное приложение для автоматизации работы с образовательным порталом edonish.tj, написанное на **Go** с использованием **Fyne GUI**.

---

## ✅ ГОТОВО! Тег v0.1.0 отправлен на GitHub

**GitHub Actions уже запущен!** Проверьте статус сборки: [Actions](https://github.com/4codegit/edonish-auto/actions)

После завершения сборки файлы появятся в [Releases](https://github.com/4codegit/edonish-auto/releases)

---

## 🚀 Скачать готовую версию

### GitHub Releases

Скачайте готовую версию для вашей платформы: [Releases](https://github.com/4codegit/edonish-auto/releases)

| Платформа | Файл | Установка |
|-----------|------|-----------|
| 🐧 Linux (DEB) | `edonish-app_x.x.x_amd64.deb` | `sudo dpkg -i file.deb` |
| 🐧 Linux (RPM) | `edonish-app-x.x.x-1.x86_64.rpm` | `sudo rpm -i file.rpm` |
| 🪟 Windows | `edonish-app-windows.exe` | Запустить напрямую |
| 🪟 Windows (Setup) | `edonish-app-windows-installer.exe` | Установщик |
| 🤖 Android | `edonish-app.apk` | Установить на устройстве |

---

## 🏃 Быстрый запуск (скачав релиз)

### Linux (Ubuntu/Debian)
```bash
sudo dpkg -i edonish-app_x.x.x_amd64.deb
sudo apt-get install -f  # если нужны зависимости
edonish-app
```

### Linux (Fedora/RHEL)
```bash
sudo rpm -i edonish-app-x.x.x-1.x86_64.rpm
edonish-app
```

### Windows
```bash
# Запустить напрямую
edonish-app-windows.exe

# ИЛИ установить
edonish-app-windows-installer.exe
```

### Android
```bash
# Включите "Установка из неизвестных источников"
# Установите APK
adb install edonish-app.apk
```

### 1. Инициализация проекта

```bash
# Создаём директорию проекта
mkdir edonish-go-app
cd edonish-go-app

# Инициализируем Go модуль
go mod init edonish-app

# Создаём структуру папок
mkdir client ui
```

### 2. Установка системных зависимостей

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y gcc libgl1-mesa-dev xorg-dev
```

**macOS:**
```bash
brew install go
brew install gcc
```

**Windows:**
```bash
# Установите MinGW-w64 через Chocolatey
choco install mingw
```

### 3. Установка зависимостей Go

```bash
# Устанавливаем Fyne и другие зависимости
go get fyne.io/fyne/v2@latest
go get github.com/PuerkitoBio/goquery@latest

# Обновляем модуль
go mod tidy
```

### 4. Запуск приложения

```bash
# Запуск в режиме разработки
go run .
```

### 5. Компиляция в исполняемый файл

```bash
# Linux
GOOS=linux GOARCH=amd64 go build -o edonish-app .

# Windows
GOOS=windows GOARCH=amd64 go build -o edonish-app.exe .

# macOS
GOOS=darwin GOARCH=amd64 go build -o edonish-app .
```

---

## 📋 Структура проекта

```
edonish-app/
├── main.go                    # Точка входа
├── controller.go              # Контроллер приложения
├── client/
│   └── client.go              # HTTP клиент для API
├── ui/
│   ├── login_screen.go        # Экран авторизации
│   └── dashboard.go           # Главное окно
├── go.mod                     # Зависимости Go
├── go.sum                     # Хеши зависимостей
└── README.md                  # Документация
```

---

## ⚙️ Настройка API Endpoints

### Изучение реальных API

**ВАЖНО:** Перед использованием необходимо изучить реальные API-эндпоинты портала edonish.tj:

1. Откройте сайт в браузере и откройте DevTools (F12)
2. Перейдите на вкладку **Network**
3. Выполните вход и найдите запросы к API
4. Обновите URL-адреса в `controller.go`:

```go
// controller.go
c.client, err = client.NewEdonishClient(
    "https://edonish.tj",              // baseURL
    "https://edonish.tj/api/auth/login", // authURL - ЗАМЕНИТЕ на реальный
)
```

### Обнаруженные endpoints (на основе Python версии)

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/auth/v1/login` | POST | Авторизация |
| `/teacher/v1/journal` | GET | Журнал оценок |
| `/teacher/v1/journal/dates` | GET | Даты журнала |
| `/teacher/v1/journal/students` | GET | Студенты с оценками |
| `/teacher/v1/journal/10_point_mark/create` | POST | Создание оценки |
| `/school_admin/v1/period/quaters` | GET | Список четвертей |

**Обновите `client/client.go`** с реальными эндпоинтами:

```go
// В структуре EdonishClient
authURL:    "https://edonish.tj/auth/v1/login",      // Авторизация
scheduleURL: "https://edonish.tj/teacher/v1/journal", // Расписание
gradesURL:   "https://edonish.tj/teacher/v1/journal/students", // Оценки
```

---

## 🏗️ Архитектура

Приложение следует принципам **чистой архитектуры**:

```
┌─────────────────┐
│     main.go     │  ← Точка входа
└────────┬────────┘
         │
┌────────▼────────┐
│  controller.go  │  ← Контроллер (связывает UI и Client)
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌──▼──────┐
│  UI  │  │ Client  │  ← HTTP клиент (отделён от UI)
└──────┘  └─────────┘
```

### Слои

- **client/** - Работа с API (HTTP запросы, JSON парсинг, cookies)
- **ui/** - Представление (виджеты Fyne, формы, таблицы)
- **controller/** - Управление потоком (логика перехода между экранами)

---

## 🔐 Авторизация

Пример входа с вашими данными:

```
Логин: 20011XXYX
Пароль: ********
```

**Безопасность:** Пароли вводятся через UI и не хранятся в коде!

---

## 📊 Функциональность

### Текущая версия

- ✅ **Login UI** - Экран авторизации с полями логин/пароль
- ✅ **Dashboard UI** - Главное окно с вкладками
- ✅ **API Client** - HTTP клиент с cookie jar
- ✅ **Обработка ошибок** - Всплывающие диалоги
- ✅ **Таблицы данных** - Отображение расписания, оценок, ДЗ

### Требуется доработка

- ⏳ **Реальные API endpoints** - Замените заглушки на реальные URL
- ⏳ **Структуры данных** - Адаптируйте под реальный JSON формат
- ⏳ **HTML парсинг** - Добавьте goquery если API закрыт
- ⏳ **Обновление данных** - Кнопка "Обновить" на дашборде

---

## 📦 Создание GitHub Release (для разработчиков)

### ✅ ТЕГ УЖЕ ОТПРАВЛЕН!

**v0.1.0 уже отправлен на GitHub!** GitHub Actions автоматически собирает все файлы.

Проверьте статус: [Actions Tab](https://github.com/4codegit/edonish-auto/actions)

После завершения файлы появятся в [Releases](https://github.com/4codegit/edonish-auto/releases)

### Создать новый Release

```bash
# Создать новый тег
git tag v0.1.1
git push origin v0.1.1
```

GitHub Actions автоматически:
- ✅ Собрать Linux бинарник
- ✅ Собрать DEB пакет (.deb)
- ✅ Собрать RPM пакет (.rpm)
- ✅ Собрать Windows бинарник (.exe)
- ✅ Собрать установщик Windows
- ✅ Собрать Android APK (.apk)
- ✅ Создать GitHub Release с файлами

### Локальная сборка всех платформ

```bash
# Сделать все для текущей платформы
bash build_all.sh v0.1.0 all

# Или конкретную платформу
bash build_linux.sh v0.1.0
bash build_windows.sh v0.1.0
bash build_android_go.sh v0.1.0
```

### Результат сборки

Все файлы будут в `release/` директории:
```
release/
├── linux/
│   ├── edonish-app-linux
│   ├── edonish-app_v0.1.0_amd64.deb
│   └── edonish-app-0.1.0-1.x86_64.rpm
├── windows/
│   ├── edonish-app-windows.exe
│   └── edonish-app-windows-installer.exe
└── android/
    └── edonish-app-0.1.0.apk
```

### Ручное создание Release

1. Перейдите на [GitHub Releases](https://github.com/YOUR_USERNAME/edonish-app/releases/new)
2. Выберите тег (создайте новый если нет)
3. Добавьте название релиза
4. Перетащите файлы из `release/`
5. Опубликуйте

---

## 🐛 Устранение проблем

### Ошибка компиляции Fyne

```bash
# Очистка кэша и перевыполнение
go clean -modcache
go mod tidy
go run .
```

### Ошибка соединения

1. Проверьте интернет-соединение
2. Убедитесь, что URL-адреса API корректны
3. Проверьте firewall/антивирус

### Ошибка парсинга JSON

1. Откройте DevTools в браузере
2. Сравните реальный ответ API со структурами в `client/client.go`
3. Обновите структуры при необходимости

---

## 📝 TODO - Что нужно сделать

1. **Изучить реальные API endpoints** через DevTools браузера
2. **Обновить структуры JSON** в `client/client.go` под реальный формат
3. **Заменить заглушки URL** на реальные эндпоинты
4. **Протестировать авторизацию** с реальным сервером
5. **Добавить обработку HTML** через goquery если API недоступен

---

## 📄 Лицензия

MIT License - образовательные цели. Используйте ответственно.

---

## 🤝 Вклад

1. Форкните репозиторий
2. Создайте ветку (`git checkout -b feature/amazing-feature`)
3. Закоммитьте (`git commit -m 'Add something'`)
4. Пушните (`git push origin feature/amazing-feature`)
5. Откройте Pull Request
