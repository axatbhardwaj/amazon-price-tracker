.PHONY: help install setup run-cli run-bot test clean

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies using uv"
	@echo "  make setup      - Install dependencies and create .env if it doesn't exist"
	@echo "  make run-cli    - Run the tracker in CLI mode (system notifications)"
	@echo "  make run-bot    - Run the Telegram bot"
	@echo "  make test       - Run tests"
	@echo "  make clean      - Remove pycache and temporary files"

install:
	uv sync

setup: install
	@if [ ! -f .env ]; then \
		echo "Creating .env file..."; \
		echo "TELEGRAM_TOKEN=your_telegram_bot_token_here" > .env; \
		echo "UPTIME_KUMA_PUSH_URL=" >> .env; \
		echo ".env file created. Please update it with your actual token."; \
	else \
		echo ".env file already exists. Skipping creation."; \
	fi

run-cli:
	uv run python tracker.py

run-bot:
	uv run python bot.py

test:
	uv run pytest

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -f .coverage
