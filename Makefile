.PHONY: run

run:
	docker-compose down -v --remove-orphans
	docker-compose up --build
