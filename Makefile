.PHONY: dev install test lint clean

dev:
	uvicorn app.main:app --reload --port 8000

deploy:
	scripts/deploy.sh

install:
	pip install -r requirements.txt

test:
	pytest

lint:
	flake8 .
	black .

clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
