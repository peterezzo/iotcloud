.PHONY: build push install ircbot all
build:
	docker context use default && docker build --pull -t iotcloud_base -f base/Dockerfile . && docker-compose -f docker-compose-build.yml build

push:
	docker context use default && docker-compose -f docker-compose-build.yml push

install:
	docker context use default && docker-compose up -d --remove-orphans

ircbot:
	docker context use iot && docker-compose -f docker-compose-ircbot.yml up -d --remove-orphans

all: build install ircbot
