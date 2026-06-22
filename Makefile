.PHONY: help backend-install backend-test backend-lint frontend-install frontend-test frontend-build infra-install infra-test infra-synth test-all

help:
	@echo "TalentLens AI — common tasks"
	@echo "  make backend-install    Install backend Python dependencies"
	@echo "  make backend-test       Run backend pytest suite"
	@echo "  make backend-lint       Run ruff lint + format check on backend/"
	@echo "  make frontend-install   Install frontend npm dependencies"
	@echo "  make frontend-test      Run frontend vitest suite"
	@echo "  make frontend-build     Build frontend production bundle"
	@echo "  make infra-install      Install CDK Python dependencies"
	@echo "  make infra-test         Run CDK assertion tests"
	@echo "  make infra-synth        Synthesize CloudFormation templates"
	@echo "  make test-all           Run backend, frontend, and infra test suites"

backend-install:
	pip install -r backend/requirements.txt

backend-test:
	python -m pytest backend/tests/ -v

backend-lint:
	ruff check backend/
	ruff format backend/ --check

frontend-install:
	cd frontend && npm install

frontend-test:
	cd frontend && npx vitest run

frontend-build:
	cd frontend && npm run build

infra-install:
	pip install -r infra/requirements.txt

infra-test:
	cd infra && python -m pytest tests/ -v

infra-synth:
	cd infra && cdk synth

test-all: backend-test frontend-test infra-test
