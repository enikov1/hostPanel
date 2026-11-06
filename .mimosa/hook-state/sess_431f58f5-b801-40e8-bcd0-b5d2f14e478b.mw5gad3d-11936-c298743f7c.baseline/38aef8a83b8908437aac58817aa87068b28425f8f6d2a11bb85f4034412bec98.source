#!/bin/bash
# Ручное обновление HostPanel до 2.21.1 из готового архива
set -e
cd /root
rm -rf up221 && mkdir up221
tar xzf hostpanel-2.21.1.tar.gz -C up221
cp -r /opt/hostpanel/panel /opt/hostpanel/panel.bak-2.21.1
rm -rf /opt/hostpanel/panel
cp -r up221/hostpanel-2.21.1/panel /opt/hostpanel/panel
echo 2.21.1 > /opt/hostpanel/VERSION
chown -R hostpanel:hostpanel /opt/hostpanel/panel /opt/hostpanel/VERSION
chmod -R go-w /opt/hostpanel/panel
systemctl restart hostpanel
sleep 3
systemctl is-active hostpanel
curl -s http://127.0.0.1:8080/api/login-state
echo
rm -rf /root/up221 /root/hostpanel-2.21.1.tar.gz
