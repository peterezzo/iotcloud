.PHONY: docker
docker:
	docker-compose --context orwell build --pull --parallel && docker-compose --context orwell up -d
