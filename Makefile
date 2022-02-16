.PHONY: docker
docker:
	docker-compose --context orwell build --pull --parallel && docker-compose --context orwell up -d --remove-orphans

.PHONY: linear
linear:
	docker-compose --context orwell build --pull && docker-compose --context orwell up -d --remove-orphans
