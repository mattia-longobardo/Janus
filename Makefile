.PHONY: help install lint test ci deploy

UV := uv run --no-project --python 3.12 --with-requirements requirements-dev.txt
CI_DB := janus-ci-db

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

install: ## Install the frontend dependencies (the backend runs through uv)
	cd frontend && npm ci

lint: ## ruff on the backend, type check on the frontend
	cd backend && $(UV) ruff check .
	cd frontend && npx tsc --noEmit

test: ## Backend tests (PostgreSQL on localhost:5432, see AGENTS.md) and frontend tests
	scripts/test.sh
	cd frontend && npm test

ci: install lint ## CI entry point: lint, then the tests against a throwaway PostgreSQL
	docker run -d --rm --name $(CI_DB) -p 127.0.0.1:5432:5432 -e POSTGRES_USER=janus -e POSTGRES_PASSWORD=janus -e POSTGRES_DB=janus_test pgvector/pgvector:pg18
	until docker exec $(CI_DB) pg_isready -U janus -d janus_test >/dev/null 2>&1; do sleep 1; done
	$(MAKE) test; status=$$?; docker stop $(CI_DB) >/dev/null; exit $$status

deploy: ## Build and start the stack from this checkout (git-policy §7)
	flock -n /var/lock/deploy-janus.lock docker compose up -d --build --wait
