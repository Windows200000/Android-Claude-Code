cc() {   # plain start: phone access (adb/Shizuku/Wireless debugging) and keep-awake are OFF; Claude turns them on only when needed, asking you first
  [ "${CC_KEEPAWAKE:-0}" = 1 ] && { timeout 50 phoneon >/dev/null 2>&1; phonekeep on 240 >/dev/null 2>&1; }   # optional: CC_KEEPAWAKE=1 cc
  proot-distro login debian -- bash -c 'mkdir -p -m 700 /root/.cc-msg; find /root/.cc-msg -name "*.sock" -mtime +1 -delete 2>/dev/null; export IS_SANDBOX=1 DISABLE_TELEMETRY=1 DISABLE_ERROR_REPORTING=1; exec /root/.local/bin/claude --allow-dangerously-skip-permissions --messaging-socket-path "/root/.cc-msg/$$-$(date +%s).sock" "$@"' claude "$@"
  phonekeep off >/dev/null 2>&1
  if pgrep -x adb >/dev/null 2>&1; then   # leftover adb server: switch access off only if a device is really connected, else just stop the server (fast)
    if timeout 2 adb devices 2>/dev/null | grep -q 'device$'; then phoneoff >/dev/null 2>&1; echo "[cc] phone access + Wireless debugging switched off"; else adb kill-server >/dev/null 2>&1; fi
  fi
}
