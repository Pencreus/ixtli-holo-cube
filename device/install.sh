#!/bin/sh
# Installs/updates the hub agent on the device over USB adb. Safe to re-run.
set -e
cd "$(dirname "$0")"
adb shell 'mount | grep -q " /overlay " || true'
adb push hubagent /usr/bin/hubagent >/dev/null
adb push hubagent.init /etc/init.d/hubagent >/dev/null
adb push secrets.env /etc/hubagent.conf >/dev/null
adb shell 'chmod 755 /usr/bin/hubagent /etc/init.d/hubagent; chmod 600 /etc/hubagent.conf; sh -n /usr/bin/hubagent && echo syntax-ok'
adb shell '/etc/init.d/hubagent enable; ls /etc/rc.d | grep hubagent'
