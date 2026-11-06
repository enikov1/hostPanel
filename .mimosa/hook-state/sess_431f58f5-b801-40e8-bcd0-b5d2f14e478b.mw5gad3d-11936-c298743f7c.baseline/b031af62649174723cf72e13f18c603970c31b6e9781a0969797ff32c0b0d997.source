#!/usr/bin/env python3
# Записывает состояние движка Omro для сайта (после ручной установки)
import sys
sys.path.insert(0, '/opt/hostpanel')
from panel.context import set_context
from panel.state import Store
store = Store('/opt/hostpanel', demo=False)
set_context(False, '/opt/hostpanel', store)
from panel.context import STATE_LOCK
import secrets

site = store.find_site(772231479)
with STATE_LOCK:
    site['engine_cld'] = True
    site['cld'] = {
        'engine': 'omro', 'version': 'main',
        'installed_at': '2026-11-06 23:24:04',
        'db_name': 'test_new1', 'db_user': 'test_new1',
        'db_password': secrets.token_urlsafe(18),
        'admin_token': secrets.token_hex(24),
    }
    store.log_action('движок Omro: состояние записано после установки')
    store.save()
print('state recorded OK')
