.PHONY: build push install all
build:
	docker context use default && \
	docker build --pull -t iotcloud_base -f base/Dockerfile . && \
	docker-compose -f docker-compose-build.yml build && \
	docker-compose pull

push:
	docker context use default && \
	docker-compose -f docker-compose-build.yml push

install:
	docker context use default && \
	docker-compose up -d --remove-orphans

all: build push install
