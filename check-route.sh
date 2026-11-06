#!/bin/bash
# проверка маршрута установки движка на сервере
grep -n 'engine/install\|engine/:engine' /opt/hostpanel/panel/api/engines.py | head -3
grep -n 'VERSION = ' /opt/hostpanel/panel/config.py | head -1
