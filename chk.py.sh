#!/bin/bash
# проверка кода движков на сервере
grep -n install /opt/hostpanel/panel/api/engines.py | head -3
grep "VERSION = " /opt/hostpanel/panel/config.py | head -1
