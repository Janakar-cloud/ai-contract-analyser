.PHONY: help build up down logs shell exec dev prod restart status clean

# Default target executed when no arguments are given to make.
help:
	@echo "Contract Anomaly Detection System Commands:"
	@echo "make build        - Build or rebuild services"
	@echo "make up           - Create and start containers in development mode (without AI services)"
	@echo "make prod         - Create and start all containers in production mode (with AI services)"
	@echo "make down         - Stop and remove containers"
	@echo "make logs         - View output from containers"
	@echo "make shell        - Start a bash shell in the app container"
	@echo "make exec         - Execute a command in the app container"
	@echo "make restart      - Restart services"
	@echo "make status       - Show status of containers"
	@echo "make clean        - Remove all containers and volumes"
	@echo "make env          - Create .env file from example"

# Build or rebuild services
build:
	docker-compose build

# Create and start containers in development mode (without AI services)
up:
	docker-compose up -d app chainlit

# Create and start containers in production mode (with AI services)
prod:
	cp .env-example .env || true
	sed -i 's/DEV_MODE=true/DEV_MODE=false/' .env
	sed -i 's/VLLM_ENABLED=false/VLLM_ENABLED=true/' .env
	sed -i 's/WEAVIATE_ENABLED=false/WEAVIATE_ENABLED=true/' .env
	docker-compose up -d

# Stop services
down:
	docker-compose down

# View output from containers
logs:
	docker-compose logs -f

# Start a bash shell in app container 
shell:
	docker-compose exec app bash

# Execute a command in app container
exec:
	@read -p "Enter command to execute in app container: " cmd; \
	docker-compose exec app $$cmd

# Restart services
restart:
	docker-compose restart

# Show status of services
status:
	docker-compose ps

# Remove all containers and volumes
clean:
	docker-compose down -v
	rm -rf .env

# Create an .env file from example
env:
	cp .env-example .env
	@echo ".env file created. You may want to edit it to adjust settings."