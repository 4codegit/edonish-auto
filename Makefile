# eDonish Auto — Makefile (Python + Go)

.PHONY: gui cli install analyze view clean help build-linux build-windows build-android build-all

# Default target
help:
	@echo "eDonish Auto — команды:"
	@echo ""
	@echo "=== Python ==="
	@echo "  make gui          — Запустить GUI (Python)"
	@echo "  make cli          — Запустить CLI с аргументами (ARGS=...)"
	@echo "  make install      — Установить Python зависимости"
	@echo "  make analyze      — Только анализ (без записи)"
	@echo "  make view         — Просмотр журнала"
	@echo ""
	@echo "=== Go/Fyne ==="
	@echo "  make go-deps      — Установить Go зависимости"
	@echo "  make go-run       — Запустить Go приложение"
	@echo "  make linux        — Собрать для Linux (binary + deb + rpm)"
	@echo "  make windows      — Собрать для Windows (exe + installer)"
	@echo "  make android      — Собрать для Android (apk)"
	@echo "  make all          — Собрать для всех платформ"
	@echo "  make go-clean     — Очистить Go сборочные файлы"

gui:
	python3 main.py

cli:
	python3 main_cli.py $(ARGS)

install:
	pip install -r requirements.txt

analyze:
	python3 main_cli.py $(ARGS) --analyze-only --save-report

view:
	python3 main_cli.py $(ARGS) --view-journal

clean:
	rm -rf logs/ output/

# Go commands
go-deps:
	go mod tidy
	go get fyne.io/fyne/v2@latest
	go get github.com/PuerkitoBio/goquery@latest

go-run: go-deps
	go run .

linux:
	@bash build_linux.sh $(shell git describe --tags 2>/dev/null || echo "dev")

windows:
	@bash build_windows.sh $(shell git describe --tags 2>/dev/null || echo "dev")

android:
	@bash build_android_go.sh $(shell git describe --tags 2>/dev/null || echo "dev")

all: linux windows android
	@echo "✅ All builds complete!"

go-clean:
	rm -rf release/ deb/ rpm/
	rm -f edonish-app-linux edonish-app-windows.exe edonish-app.apk
	go clean
