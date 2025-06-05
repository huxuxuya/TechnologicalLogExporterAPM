#!/bin/bash

echo "Stopping Elasticsearch, Kibana, and APM Server..."

# Stop the containers
docker-compose down

echo "All services have been stopped." 