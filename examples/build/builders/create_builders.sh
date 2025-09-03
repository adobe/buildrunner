#!/bin/bash

docker buildx create --name builder1 --driver docker-container --bootstrap
docker buildx create --name builder2 --driver docker-container --bootstrap
docker buildx create --name builder3 --driver docker-container --bootstrap

docker buildx ls --debug