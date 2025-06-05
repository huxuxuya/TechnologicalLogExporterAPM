#!/bin/bash

echo "Starting Elasticsearch, Kibana, and APM Server..."

# Increase virtual memory for Elasticsearch
echo "Increasing virtual memory limits..."
sudo sysctl -w vm.max_map_count=262144

# Start the containers
docker-compose up -d

echo "Waiting for services to start..."
sleep 30

echo "Checking service status..."

# Check Elasticsearch
echo "Checking Elasticsearch..."
curl -s http://localhost:9200/_cluster/health | grep -q 'status.*green\|status.*yellow' && echo "Elasticsearch is running" || echo "Elasticsearch is not healthy"

# Check Kibana
echo "Checking Kibana..."
curl -s http://localhost:5601/api/status | grep -q "Looking good" && echo "Kibana is running" || echo "Kibana is not healthy"

# Check APM Server
echo "Checking APM Server..."
curl -s http://localhost:8200/ | grep -q "ok" && echo "APM Server is running" || echo "APM Server is not healthy"

echo "
Services are ready!

Elasticsearch: http://localhost:9200
Kibana:        http://localhost:5601
APM Server:    http://localhost:8200

You can now run your log processing scripts:

For Elasticsearch:
python log_to_elastic.py http://localhost:9200 your_log_file.log

For APM:
python log_to_apm.py http://localhost:8200 your_log_file.log
" 