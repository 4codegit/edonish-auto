# eDonish Auto — Makefile

.PHONY: gui cli install analyze view clean help

# Default target
help:
	@echo "eDonish Auto — команды:"
	@echo ""
	@echo "  make gui          — Запустить GUI"
	@echo "  make cli          — Запустить CLI с аргументами (ARGS=...)"
	@echo "  make install      — Установить зависимости"
	@echo "  make analyze      — Только анализ (без записи)"
	@echo "  make view         — Просмотр журнала"
	@echo "  make clean        — Очистить логи и отчёты"

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
