#!/bin/bash
# Проверка эндпоинта установки движка после фикса роутинга
curl -s -X POST http://127.0.0.1:8080/api/login \
  -H 'Content-Type: application/json' -H 'Origin: http://127.0.0.1:8080' \
  -d '{"login":"admin","password":"tX6xhzsjVmtjtgWU"}' -c /tmp/hpapi.txt > /dev/null

echo '=== POST /api/site/772231479/engine/install (omro):'
curl -s -b /tmp/hpapi.txt -X POST http://127.0.0.1:8080/api/site/772231479/engine/install \
  -H 'Content-Type: application/json' -H 'Origin: http://127.0.0.1:8080' \
  -d '{"engine":"omro","db_mode":"new","confirm_overwrite":true}' | head -c 150
echo
sleep 3
echo '=== статус:'
curl -s -b /tmp/hpapi.txt http://127.0.0.1:8080/api/site/772231479/engine | head -c 200
echo
