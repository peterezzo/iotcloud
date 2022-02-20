.PHONY: default
default:
	docker-compose build --pull && docker-compose up -d --remove-orphans

.PHONY: parallel
parallel:
	docker-compose build --pull --parallel  && docker-compose up -d --remove-orphans

.PHONY: remote
remote:
	docker-compose --context orwell build --pull && docker-compose --context orwell up -d --remove-orphans

.PHONY: parallel-remote
linear-remote:
	docker-compose --context orwell build --pull --parallel && docker-compose --context orwell up -d --remove-orphans
