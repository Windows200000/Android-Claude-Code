# cross-session messaging needs a private socket path under proot (no uid mapping)
claude() { mkdir -p -m 700 "$HOME/.cc-msg"; command claude --allow-dangerously-skip-permissions --messaging-socket-path "$HOME/.cc-msg/$$-$(date +%s).sock" "$@"; }
