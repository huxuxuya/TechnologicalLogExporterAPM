#!/bin/sh
set -e

KIBANA_SYSTEM_PASSWORD=changeme

# Ждём, пока Elasticsearch не станет доступен
until curl -s -u elastic:$ELASTIC_PASSWORD http://elasticsearch:9200/_cluster/health | grep -q '"status"'; do
  echo "Waiting for Elasticsearch..."
  sleep 2
done

# Устанавливаем пароль для kibana_system
echo "Setting password for kibana_system..."
curl -s -X POST -u elastic:$ELASTIC_PASSWORD "http://elasticsearch:9200/_security/user/kibana_system/_password" \
  -H "Content-Type: application/json" \
  -d "{\"password\":\"$KIBANA_SYSTEM_PASSWORD\"}"

echo "Password for kibana_system set successfully." 