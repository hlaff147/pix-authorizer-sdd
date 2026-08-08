.PHONY: up down test test-contract logs clean

up:
	docker-compose up --build -d

down:
	docker-compose down -v

test:
	pytest tests/ -v

test-contract:
	pytest tests/test_contract.py -v

logs:
	docker-compose logs -f app

clean:
	docker-compose down -v --remove-orphans
