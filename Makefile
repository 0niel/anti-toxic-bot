.PHONY: format build run stop restart clean logs shell prune help

# Formatting commands
format:
	isort --force-single-line-imports .
	autoflake --remove-all-unused-imports --recursive --remove-unused-variables --in-place . --exclude=__init__.py
	black .
	isort --recursive --apply .

# Docker commands
build:
	docker build -t tg-bot .

run:
	docker run --env-file .env -p 5000:5000 --name tg-bot tg-bot

stop:
	docker stop tg-bot
	docker rm tg-bot

restart: stop build run

clean:
	docker rmi tg-bot

logs:
	docker logs -f tg-bot

shell:
	docker exec -it tg-bot /bin/sh

prune:
	docker system prune -f
	docker volume prune -f

# Default goal
.DEFAULT_GOAL := help

# Help target to list available commands
help:
	@echo "Available commands:"
	@echo "  format  - Run code formatting tools"
	@echo "  build   - Build the Docker image"
	@echo "  run     - Run the Docker container"
	@echo "  stop    - Stop and remove the Docker container"
	@echo "  restart - Stop, rebuild and run the Docker container"
	@echo "  clean   - Remove the Docker image"
	@echo "  logs    - Show logs of the running container"
	@echo "  shell   - Open a shell inside the running container"
	@echo "  prune   - Remove all unused Docker objects"
