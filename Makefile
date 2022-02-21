.PHONY: default parallel ircbot all
default:
	docker context use default && docker-compose build --pull && docker-compose up -d --remove-orphans

parallel:
	docker context use default && docker-compose build --pull --parallel  && docker-compose up -d --remove-orphans

ircbot:
	docker context use iot && docker-compose -f docker-compose-ircbot.yml build --pull && docker-compose -f docker-compose-ircbot.yml up -d --remove-orphans

all: default ircbot
