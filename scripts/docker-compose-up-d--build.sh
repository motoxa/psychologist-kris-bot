#!/bin/sh

docker compose up -d --build && docker builder prune -af && docker image prune -f
