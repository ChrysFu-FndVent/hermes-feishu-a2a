.PHONY: install lint test security run docker-up validate

install:
	python -m pip install -e '.[dev]'

lint:
	ruff check .

test:
	pytest

security:
	python scripts/check_secrets.py

run:
	hermes-a2a serve

docker-up:
	docker compose up --build -d

validate:
	hermes-a2a validate-config --path config/agents.example.yaml
