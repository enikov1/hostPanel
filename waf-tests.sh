#!/bin/bash
# Тесты всех функций WAF на живом сайте (garri-pottertv.net)
H='Content-Type: application/json'
O='Origin: http://127.0.0.1:8080'
CK='-b /tmp/hpapi.txt'
URL='http://127.0.0.1:8080/api/sites/security'
TGT='https://garri-pottertv.net/'
T() { curl -sk -o /dev/null -w '%{http_code}' --resolve garri-pottertv.net:443:127.0.0.1 "$@" "$TGT"; }
apply() { curl -s $CK -X POST "$URL" -H "$H" -H "$O" -d "$1" >/dev/null; sleep 1; nginx -s reload >/dev/null 2>&1; sleep 1; }

echo '=== Т0: база (без фильтров) — ожидаем 200'
apply '{"id":772231479,"security":{"geo_allow":[],"geo_deny":[],"block_empty_ua":false,"ref_block":[],"ref_allow":[],"block_empty_ref":false,"block_bots":false,"waf":false,"rate_limit":0,"rate_burst":20}}'
echo "результат: $(T)"

echo '=== Т1: категория scanners — sqlmap 403, Mozilla 200'
apply '{"id":772231479,"security":{"geo_allow":[],"geo_deny":[],"ua_categories":["scanners"],"block_empty_ua":false,"ref_block":[],"ref_allow":[],"block_empty_ref":false,"block_bots":false,"waf":false,"rate_limit":0,"rate_burst":20}}'
echo "sqlmap: $(T -A 'sqlmap/1.5')  Mozilla: $(T -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')"

echo '=== Т2: категория http_tools — python-requests 403, Googlebot 200 (allow выше deny)'
apply '{"id":772231479,"security":{"geo_allow":[],"geo_deny":[],"ua_categories":["http_tools"],"block_empty_ua":false,"ref_block":[],"ref_allow":[],"block_empty_ref":false,"block_bots":false,"waf":false,"rate_limit":0,"rate_burst":20}}'
echo "python-requests: $(T -A 'python-requests/2.31')  Googlebot: $(T -A 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)')"

echo '=== Т3: блокировка пустого User-Agent'
apply '{"id":772231479,"security":{"geo_allow":[],"geo_deny":[],"ua_categories":[],"block_empty_ua":true,"ref_block":[],"ref_allow":[],"block_empty_ref":false,"block_bots":false,"waf":false,"rate_limit":0,"rate_burst":20}}'
echo "без UA: $(T -A '')  с UA: $(T -A 'Mozilla/5.0')"

echo '=== Т4: чёрный список рефереров'
apply '{"id":772231479,"security":{"geo_allow":[],"geo_deny":[],"ua_categories":[],"block_empty_ua":false,"ref_block":["spam-site.com"],"ref_allow":[],"block_empty_ref":false,"block_bots":false,"waf":false,"rate_limit":0,"rate_burst":20}}'
echo "spam-site.com: $(T -e 'https://spam-site.com/page')  yandex.ru: $(T -e 'https://yandex.ru/')"

echo '=== Т5: WAF — SQLi и .env 403, чистый запрос 200'
apply '{"id":772231479,"security":{"geo_allow":[],"geo_deny":[],"ua_categories":[],"block_empty_ua":false,"ref_block":[],"ref_allow":[],"block_empty_ref":false,"block_bots":false,"waf":true,"rate_limit":0,"rate_burst":20}}'
echo "SQLi: $(T 'https://garri-pottertv.net/?id=1+UNION+SELECT+password+FROM+users')  .env: $(T 'https://garri-pottertv.net/.env')  wp-config: $(T 'https://garri-pottertv.net/wp-config.php')  чистый: $(T)"

echo '=== Т6: rate limit 5 р/с burst 10 — 40 запросов подряд'
apply '{"id":772231479,"security":{"geo_allow":[],"geo_deny":[],"ua_categories":[],"block_empty_ua":false,"ref_block":[],"ref_allow":[],"block_empty_ref":false,"block_bots":false,"waf":false,"rate_limit":5,"rate_burst":10}}'
OUT=''; for i in $(seq 1 40); do OUT="$OUT $(T -A 'Mozilla/5.0')"; done
echo "$OUT" | tr ' ' '\n' | sort | uniq -c | sort -rn | awk '{printf "  %s x%s\n", $2, $1}'

echo '=== Т7: свои UA-правила (regex grep)'
apply '{"id":772231479,"security":{"geo_allow":[],"geo_deny":[],"ua_categories":[],"ua_rules":[{"pattern":"BadBot|MyScraper","note":"тест"}],"block_empty_ua":false,"ref_block":[],"ref_allow":[],"block_empty_ref":false,"block_bots":false,"waf":false,"rate_limit":0,"rate_burst":20}}'
echo "MyScraper: $(T -A 'MyScraper/1.0')  Mozilla: $(T -A 'Mozilla/5.0')"

echo '=== Т8: гео deny RU (сервер в RU) — 403'
apply '{"id":772231479,"security":{"geo_allow":[],"geo_deny":["RU"],"ua_categories":[],"block_empty_ua":false,"ref_block":[],"ref_allow":[],"block_empty_ref":false,"block_bots":false,"waf":false,"rate_limit":0,"rate_burst":20}}'
echo "deny RU: $(T)"

echo '=== Т9: гео allow DE (сервер в RU) — 403'
apply '{"id":772231479,"security":{"geo_allow":["DE"],"geo_deny":[],"ua_categories":[],"block_empty_ua":false,"ref_block":[],"ref_allow":[],"block_empty_ref":false,"block_bots":false,"waf":false,"rate_limit":0,"rate_burst":20}}'
echo "allow DE: $(T)"

echo '=== Т10: комбо allow BY + deny RU (сервер RU) — 403'
apply '{"id":772231479,"security":{"geo_allow":["BY"],"geo_deny":["RU"],"ua_categories":[],"block_empty_ua":false,"ref_block":[],"ref_allow":[],"block_empty_ref":false,"block_bots":false,"waf":false,"rate_limit":0,"rate_burst":20}}'
echo "combo: $(T)"

echo '=== Возврат настроек пользователя (allow BY) — ожидаем 403 для сервера (RU):'
apply '{"id":772231479,"security":{"geo_allow":["BY"],"geo_deny":[],"ua_categories":[],"block_empty_ua":false,"ref_block":[],"ref_allow":[],"block_empty_ref":false,"block_bots":false,"waf":false,"rate_limit":0,"rate_burst":20}}'
echo "итог: $(T)"
