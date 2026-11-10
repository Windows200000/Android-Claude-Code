# Claude Code on an Android phone (standalone, via Termux + Debian)

> Written while doing this for real on a Samsung S24 Ultra (Android 17, Play-build Termux) from a Windows 11 PC.
> Audience: another Claude Code instance guiding a user through this. Adapt to the user's phone and OS.
>
> **How to read this:** the sections are in the order things were discovered, so later sections can supersede earlier ones.
> The current, recommended design is **FINAL DESIGN** (`cc`, opt-in phone access) plus **BEST PC-FREE ACCESS** (`adbself`).
> The sections about moving to F-Droid Termux describe an approach that **failed on Android 17**.
> Helper scripts mentioned by name (`adbself`, `phonectl`, `phoneon`, `phoneoff`, `phonekeep`) are small scripts in Termux's `$PREFIX/bin`
> and are not part of this repository; the guide describes them precisely enough to rewrite them, and `adbsh` is reproduced in full.

## START HERE (for Claude): brief the user, ask once, then work without interrupting them
**1. Tell the user, in 3-4 lines max:** "I'll install Termux and a Debian Linux inside it, then Claude Code, so
Claude Code runs on your phone itself (no PC needed afterwards). Optional extras give it phone features and
system-level access. I need a few choices first; after that I'll do everything myself and only ping you for
steps that physically need your fingers."

**2. Ask ALL questions in ONE batch (e.g. a single AskUserQuestion call), then never ask again unless something breaks.**
Each option must say up front whether it needs the user's hands, so the answer is final and nothing blocks later.

| # | Question | Options (mark interactive ones) |
|---|---|---|
| 1 | Where do the installs come from? | **F-Droid (recommended)**: auto-updates for Termux + add-ons. Needs you to tap *Install* once for the F-Droid app, and *Allow* for "install unknown apps" for your browser/F-Droid (one-time, I'll prompt you in a single batch). / GitHub APKs: no auto-updates, same taps. |
| 2 | How do I run the setup? | **PC-assisted over USB** (needs a PC with adb; I do the typing; you must unlock the phone and approve *USB debugging*) / **Phone-only** (you paste one command into Termux; no PC) |
| 3 | Optional extras: pick any | **Termux:API** (clipboard, notifications, battery, camera, location, SMS... Claude can use them; installs one extra app; needs a one-time tap per Android permission you choose in Q4) / **Termux:GUI** (native UI from scripts; one extra app) / **Shizuku shell access** (see below) / **Termux:Boot** (autostart; one extra app) |
| 4 | If Termux:API: which phone permissions may I grant it? | camera / location / SMS / contacts / call log / microphone (none by default; each is a privacy grant) |
| 5 | Dev tools in the Linux? | **Minimal (recommended)**: git, curl, ripgrep only; Claude installs Node/Python/gcc later when a project needs it. / Add Node + Python now (~300 MB). Never default to build-essential/npm: it is slow and huge. |
| 6 | Battery | **Exempt only Termux from battery optimization (recommended, reversible)** / skip. Never apply the global phantom-process fix unless sessions actually get killed. |
| 7 | Storage tight? | Offer to strip docs/locale/man/python after install (~70-110 MB) |

**Shizuku** (explain in one sentence when offering): gives Termux commands the power of `adb shell` (silent app
install, `pm grant`, settings, reading other apps' data folders) without a PC. Costs: needs the Shizuku app (F-Droid);
**one popup on the phone that only the user can tap ("Allow all the time")**; it must be **restarted after every reboot**
(one USB command from a PC, or Wi-Fi pairing without one). Optional; skip unless the user wants it.

**3. Be transparent about everything that gets installed** (show this list before starting):
- Phone: F-Droid app (if chosen), **Termux**, optionally Termux:API, Termux:GUI, Termux:Boot, Shizuku.
- Inside Termux: `proot-distro`, a **Debian** container (~350 MB base; ~700 MB total with Claude Code, which alone is ~320 MB), `termux-api`/`termux-gui-package` if chosen, `rish` if Shizuku.
- Inside Debian: curl, git, ripgrep, ca-certificates, **Claude Code** (official native installer).
- PC (only for the assisted path): Google's **Android CLI** (+ `android init`), **platform-tools/adb** via `android sdk install platform-tools`.

**4. Interaction rules so the user is never stuck waiting on you:**
- Do every non-interactive step first. Batch the steps that need the user's hands (install-unknown-apps toggle,
  F-Droid installs, Shizuku popup, **Claude login**) into **one** list and tell them what to tap, in order.
- The user's own login to Claude is always theirs to do; never touch credentials.
- Before typing into the phone: unlocked? `adb devices` says `device`? screenshot = plain shell prompt? (see rules below.)
- If the user says "setup script" they mean **this document**.

## Big file transfers over flaky USB: pull in verified pieces (a plain `adb pull` of 17 GB died at 32%)
`adb pull` aborts when adb drops (observed every ~0.6-2 GB on this setup, USB/driver flakiness, no phone lock involved), so a
single long pull never finishes. Instead stream 1 GiB pieces and make each piece resumable:
`cmd /c "adb exec-out \"dd if=/sdcard/Download/x.tar.gz bs=1048576 skip=<i*1024> count=1024 2>/dev/null\" > part<i>"`; accept a piece
only if its size is exact, retry up to 8x (restart the adb server when `devices` is empty), skip pieces already complete on rerun,
then join and compare SHA-256 with the phone-side `sha256sum`. Needs no extra space on the phone. Run it as ONE background task and
do not use adb in parallel: the script's `adb kill-server` kills other adb calls (it ate my typed input once).
Also: turn on *Stay awake while charging* for unattended work (`adb shell settings put global stay_on_while_plugged_in 3`, undo with 0),
and never run `Start-Sleep` chains; wait on a monitor instead. `adb exec-out` redirected by `cmd /c ... > file` is binary-safe; PowerShell pipes are not.

## BEST PC-FREE ACCESS (verified): Termux's OWN adb over Wireless debugging + `adbself` (no PC, no Shizuku needed)
One-time pairing, then Termux itself has a full adb shell (uid=shell) to the phone, also reachable from Debian where Claude Code runs.
- Needs: `pkg install android-tools nmap` (already in the restored Termux), Wi-Fi connected (not internet), Developer options > Wireless debugging ON.
- **Pair once.** The pairing dialog vanishes when Termux comes to the front, so run a Termux script that WAITS in the background for a file
  `/sdcard/Download/.pairing` ("IP:PORT CODE"), then from the PC: open Settings > Developer options > Wireless debugging > *Pair device with pairing
  code*, read code + IP:port from the dialog with `uiautomator dump`, write the file; the script runs `adb pair IP:PORT CODE` and `adb connect <connect addr>`
  (the "IP address & Port" shown on the Wireless debugging page). A user can also type it by hand with split-screen. Pairing survives reboots.
- **`adbself`** (a small script in `$PREFIX/bin`): `adbself status | shell <cmd> | shizuku`.
  Reconnects to `127.0.0.1:<port>`: tries the last port, else scans localhost `nmap -p 30000-60000 --open` and tries `adb connect` on each hit
  (the TLS port changes whenever Wireless debugging is switched on; Termux's adb has **no mDNS**). ~25 s when it must scan.
- Verified: loopback (127.0.0.1) works, not just the Wi-Fi IP; simulated "reboot" by switching `adb_wifi_enabled` 0 -> 1 (port 46179 -> 44701), adbself found the new
  port and reconnected automatically; works from Debian (`proot-distro login debian -- adbself shell id -un`).
- **Restart Shizuku with no PC**: `adbself shizuku` (runs the app's `libshizuku.so` starter). The Termux->Shizuku authorization persists across restarts, so
  `adbsh` works again immediately with no popup. After a reboot: open Termux, make sure Wireless debugging is ON (one tap if it reset), run `adbself shizuku`.
- Official Shizuku 13.x only has "Start on boot (root)". Forks (e.g. thedjchi/Shizuku) add start-on-boot via WRITE_SECURE_SETTINGS; not installed.
- **Not tested on purpose:** whether Wireless debugging stays ON after a real reboot (a phone that must keep an alarm app running was not rebooted unattended). If it
  resets, the user flips the toggle once. `adb tcpip 5555` would pin the port but opens a weaker network listener; not used.
- Capabilities confirmed through Termux's adb (counts only for private data): silent `pm install -r` (no taps), `uiautomator dump`, `input` events, `screencap`,
  `dumpsys` (notifications, battery, window focus), `logcat`, `settings put/get/delete`, `appops`, `pm grant`, other apps' folders under
  `/sdcard/Android/data` (readable), the system services via `cmd -l`, `content query` for SMS/contacts/call log. Not possible: root, Samsung Secure Folder (user 150).
- "Stay awake" is *Controlled by admin* on managed phones; a screen-off timeout of 10 min can be enforced by the employer. Keep the screen alive by sending a
  harmless key (`input keyevent KEYCODE_SHIFT_LEFT`) every ~45 s from the PC; stop before any alarm time and never act when something unexpected is in the foreground.

## FIX: "Cross-session messaging is off ... user namespace without a uid mapping" (Claude Code inside proot/Debian)
Cause (from `--debug-file`): `[uds-messaging] Failed to set up sockets directory /tmp/cc-socks ... refusing to bind`: proot has no uid map, ownership can't be verified.
Fix = pass `--messaging-socket-path <SOCKET FILE>` where (a) the path is a **socket file**, not a directory (a directory gives EADDRINUSE) and
(b) its **parent directory is mode 0700** (`/root/.claude`, mode 755, is rejected). Use a private parent and a unique file per session:
`mkdir -p -m 700 /root/.cc-msg; claude --messaging-socket-path "/root/.cc-msg/$$-$(date +%s).sock"`. Verified: `[uds-messaging] Listening: /root/.cc-msg/<pid>-<ts>.sock`.
Applied in Termux's `cc()` launcher (`~/.bashrc`, also prunes sockets older than a day) and as a `claude()` function in Debian's `/root/.bashrc`.
Sessions started before the fix keep the warning until restarted. The line "6 MCP servers need authentication" is separate (account connectors; `/mcp`).
Tip: to work on a phone where the user has a Claude session open, never type into that session: open a new Termux session (drawer swipe from the left edge > **+**),
and switch back with the drawer when done.

## FINAL DESIGN (revised by the user): `cc` = plain start; phone access and keep-awake are OPT-IN, Claude asks first
User decision: keep-awake OFF by default, Claude turns it on only when necessary; adb/Shizuku access only when necessary, and Claude must ask the user first.
(This replaces an earlier "automatic" `cc`, which ran `phoneon` and a key-press loop on every start.)
`cc` (function in Termux `~/.bashrc`) now only starts Claude Code in Debian with the private messaging socket (`--messaging-socket-path`, see the messaging fix), and runs `phonekeep off` when Claude exits.
- **Phone access:** off until needed. Claude's guide says: try the no-adb tier first; if shell-level power is really needed, ask the user ("Switch on phone access? Wireless debugging + Shizuku, ~20 s"), then `phoneon`; when done, offer `phoneoff`.
- **Keep-awake:** `phonekeep on [minutes]` (default 120, auto-stops; key press `input keyevent 59` every 45 s + `termux-wake-lock`; refuses with exit 2 if phone access is off) / `phonekeep off` / `phonekeep status`. Claude uses it only when a long unattended task would hit the screen timeout, after asking.
- **Opt-in for the user:** `CC_KEEPAWAKE=1 cc` runs `phoneon` + `phonekeep on 240` before starting Claude.
- Tested: access off -> `phonekeep on` refused; `phoneon` -> `phonekeep on/status/off` OK; plain `cc -p` answered and left access off and keep-awake off.
- **Wireless debugging is switched OFF again:** `phoneoff` now also switches Wireless debugging off (`phoneoff -k` keeps it on), and `cc` runs `phoneoff` when Claude exits if an adb server is still running (prints `[cc] phone access + Wireless debugging switched off`). Plain `cc` never switches anything on. Cause of the "always on" complaint: the old `phoneoff` left Wireless debugging on unless given `-w`. Consequence: `phoneon` needs the user to flip the Wireless debugging toggle first (nothing can switch it on without adb); Claude asks for that as part of its "switch on phone access?" question.
- **Startup speed (measured):** `cc`'s own wrapper costs only ~0.7 s (`proot-distro login` 0.4 s, `claude --version` 0.4 s). The real delay was Claude Code's startup telemetry/error-reporting network calls: a headless `claude -p` took ~5.3 s, ~2.5 s with `DISABLE_TELEMETRY=1 DISABLE_ERROR_REPORTING=1` (now exported by `cc`). `DISABLE_AUTOUPDATER` alone does nothing; `--bare` is not usable (needs an API key, "Not logged in"). Second cause, in my own cleanup: `phoneoff` port-scanned for up to 40 s when a stale adb server existed but Wireless debugging was already off. Now `phoneoff` only uses an existing adb connection, and `cc` on exit checks `adb devices` (2 s timeout), else just stops the adb server. Result: plain `cc -p` ~3 s end to end.
- **Trusted folder (user request):** Debian's `/root` (where `cc` starts Claude) is marked trusted so Claude Code skips the trust dialog: set `projects["/root"].hasTrustDialogAccepted = true` in `/root/.claude.json` (the Debian image has python3 but not jq, so edit the JSON with python3; keep a backup copy first). Do this in every new setup, after the first Claude start created the file. If a running Claude session overwrites the file later, re-run the script.
- Gotcha: when deleting an old function from `.bashrc` with sed, match the line start only (`/^_cc_ka() {/,/^}$/`); a trailing comment on the line broke the exact-line pattern and left an orphan.
Claude learns its toolbox from `/root/.claude/CLAUDE.md` in Debian (marked `<!-- phone-toolbox:start/end -->`): how to check/enable access, `phonectl`/`adbsh`/`adbself`,
what works with no adb, what doesn't, privacy rules (counts not contents), never bypass locks/security prompts. Only our marked section is ever replaced; the user's own CLAUDE.md text is kept.
Limits: `phoneon` works only if Wireless debugging is ON (needs Wi-Fi); if it is off, Claude tells the user to switch it on, otherwise it stays in the no-adb tier.
A screen-off timeout enforced by an employer is beaten by the key-press loop (`phonekeep`), not by settings.

## NO-ADB MAP, COMPLETE (Play-build Termux, Android 17, no root; "no adb" = plain app permissions, nothing started by adb/Shizuku)
Works: shared storage incl. DCIM/Documents (all-files), internet, local ports, `am`/`termux-open`/broadcasts from Termux, and Termux:API: battery, clipboard, notification, toast, vibrate, volume,
microphone (Termux:API visible), audio-info, **download** (DownloadManager), job-scheduler, keystore, media-player, media-scan, usb list.
Does not work: TTS, flashlight, sensors, location, SMS, contacts, call log, Wi-Fi info/scan, notification list, cell info, NFC, infrared, camera photo, Termux:GUI (plugin cannot connect),
other apps' private folders (`/sdcard/Android/data`). Cause: the **Play build of Termux disables/blocks parts of Termux:API** (it prints "not yet available on Google Play", issue
termux-play-store/termux-apps#29) and the rest hang; keeping the Termux:API app in the foreground changes nothing; `termux-api` 0.60.0 changes nothing; F-Droid Termux cannot run on Android 17.
Only a custom helper app (loopback API + token, runtime permissions, optional Accessibility/Notification services) could restore those features without adb: it widens the phone's attack
surface, so it is left as a decision for the user (not built unattended).

## USER DECISION: nothing automatic. Access is switched on/off ON DEMAND with `phoneon` / `phoneoff`
(Supersedes the "once-per-boot hook" idea in the next section: the user explicitly does NOT want anything that runs at every boot or session start.)
- `phoneon`: connects Termux's own adb (finds the Wireless-debugging port by scanning localhost) and starts Shizuku; prints "Phone access is ON" or tells the user exactly what to
  switch on (Wireless debugging needs Wi-Fi). `phoneoff [-w]`: stops Shizuku, disconnects adb, with `-w` also switches Wireless debugging off.
  Verified cycle: `phoneoff` -> `adbsh` dead -> `phoneon` (new port) -> `adbsh` = shell.- Do not add `.bashrc`/boot persistence without the user's explicit yes (Claude's auto-mode safety check blocks it). Good fallbacks the user can pick later: Samsung Routines or
  Automate "open Termux" at boot, still followed by the user typing `phoneon`.

## NO-ADB TIER: what works and why Termux:API is half dead (tested, with a rollback each time)
- Works with no adb at all: all shared storage (all-files access), internet, Claude Code in Debian, dev servers, and the Termux:API calls battery, clipboard, notifications, toast,
  vibrate, volume, microphone (needs the Termux:API app visible).
- Dead: TTS, flashlight, Wi-Fi info, sensors, location, SMS, contacts, call log, camera photo (calls hang, exit 124). Root cause: Play-build Termux + F-Droid Termux:API 0.53.0 app (different signing
  keys; `Unable to start service com.termux.api/.TermuxApiService: not found`), not the package version.
- Tried: the Play Termux uses the old `termux.net` mirror (only termux-api 0.59.1); official `packages.termux.dev` has **0.60.0** (verified against the repo index SHA-256 `b83c85e0...` and installed with
  `dpkg -i`): **0 of 8 features fixed**, auto-rolled back to 0.59.1. `termux-am` 0.8.0-2 is already installed. No F-Droid Termux available on Android 17 (see outcome section).
- Real ways to get these features back without adb: (1) a small custom bridge app (loopback HTTP + token) that holds the runtime permissions and exposes SMS/contacts/call log/location/camera/torch/TTS,
  plus an Accessibility service (UI tree, taps, text, global actions, screenshot) and a Notification listener; one-time setup, survives reboots, no Wi-Fi/adb; (2) Automate
  flows triggered by intents. Both change the phone's attack surface (Accessibility/notification access): do only with the user's explicit approval.

## What works WITHOUT Wireless debugging, and what does not (explored on Android 17, Galaxy S24 Ultra, no root)
- Shell-level access needs adb: USB (PC) or Wireless debugging (Wi-Fi). There is **no persistent shell channel after a reboot without one of them**.
- `adb tcpip 5555` from Termux's own adb works and `127.0.0.1:5555` gives a shell **even with Wireless debugging switched off** (tested). It is **not persistent**:
  `persist.adb.tcp.port` stays empty, so it vanishes at reboot; restarting adbd (tcpip/usb) also kills a running Shizuku (restart with `adbself shizuku`). Port 5555 is a
  weaker network listener than Wireless debugging (key auth only), so only pin it briefly. `svc wifi disable` did nothing from the shell (policy), so "works with Wi-Fi off" is untested.
- Survey (read-only): Shizuku itself already holds WRITE_SECURE_SETTINGS (so an app *could* toggle Wireless debugging); automation apps such as LlamaLab **Automate** and Samsung
  Routines can run actions at boot; check what the phone has (accessibility services, notification listeners, any Device Owner / managed profile; Samsung Secure Folder is a separate profile owner).
- Practical PC-free reboot recovery needs one launcher at boot: (1) an automation app (Automate flow "device boot > wait for Wi-Fi > start Termux", plus
  `pm grant com.llamalab.automate android.permission.WRITE_SECURE_SETTINGS` if it should also flip Wireless debugging) or a Samsung routine, and (2) a once-per-boot hook
  in `~/.bashrc` that runs `adbself shizuku`. **The auto-mode classifier refused to install the .bashrc hook ("unauthorized persistence")**:
  it must be a decision of the user, not done silently. Without them the manual path is: open Termux, make sure Wireless debugging is ON, run `adbself shizuku`.
- Termux:Boot does not work with the Play build of Termux.

## `phonectl`: one command for Claude to drive the phone (verified; a script in `$PREFIX/bin`)
Wraps `adbsh` (Shizuku shell). Subcommands: `battery | fg | shot [file] | ui | tap X Y | swipe X1 Y1 X2 Y2 [ms] | text "str" | key KEYCODE | home | back | wake |
open <pkg> | install <apk> | grant/revoke <pkg> <perm> | apps | wifi | settings get|put ... | sms [n] | contacts [pat] | calls [n] | notif`.
`ui` lists on-screen text with bounds (parse `uiautomator dump`), so Claude can find and tap things. `sms/contacts/calls/notif` print private data: only on request.
Verified from Termux AND from Debian; **Claude Code on the phone ran `phonectl battery` by itself** (`claude -p ... --allowedTools "Bash(phonectl:*)"`) and answered.
This also replaces the Termux:API calls that don't work with the Play-build Termux (SMS, contacts, call log, Wi-Fi). Not replaced: TTS, torch, camera photo, sensors list.
Reminder for whoever sets up a phone: grant Claude's `--allowedTools` for `phonectl`, `adbsh`, `adbself` instead of broad Bash access.

## OUTCOME of the Play -> F-Droid Termux migration attempt on Android 17 (Galaxy S24 Ultra): FAILED, rolled back, data intact
Both F-Droid Termux 0.118.3 (stable) and 0.119.0-beta.3 installed (after the user tapped Play Protect > *Install anyway*) but **could not start**
(`error=13 Permission denied` running the bootstrap second-stage script). Rolled back: `adb uninstall com.termux`, then reinstalled the saved Play APK
splits with `adb install-multiple base.apk split_*.apk` (no popup), re-applied permissions/battery exemption, launched it (it boots to a prompt; one
"nearby devices" permission popup), restored the verified backup with the script, force-stopped and relaunched Termux.
**The restore worked perfectly**: `tar exit=0`, 0 warnings, 99,758 entries; a before/after snapshot diff was identical (212 packages+versions, every home
top-level dir's file count, git repos, config/md5 checksums, 129 Debian packages, Claude Code 2.1.318); only the font size setting (stored in Termux's own prefs)
resets. Restore took ~3 min for 21 GB. So: on Android 17 today the **Play build is the only Termux that runs**; the half-working Termux:API
(F-Droid app + Play Termux) stays; use the shell bridge (`adbsh`: `content query`, `dumpsys`, ...) for SMS/contacts/call log/Wi-Fi/sensors.
Lesson for the guide's questionnaire: check `getprop ro.build.version.sdk`; if >= 36 warn that F-Droid Termux may not run and do NOT uninstall the
working Termux before the replacement boots to a prompt.

## WARNING found on Android 17 (Galaxy S24 Ultra): F-Droid *stable* Termux 0.118.3 could not bootstrap
Install worked only after the user tapped **Play Protect "Unsafe app blocked ... built for an older version of Android" > Install anyway** (an
`adb install` hangs behind that popup; Claude's auto-mode refused to tap it: the user must). Then Termux's first run failed with
**"Unable to install bootstrap"**; logcat (`logcat -d -b all | grep Termux:TermuxInstaller`) shows
`Cannot run program ".../usr/etc/termux/bootstrap/termux-bootstrap-second-stage.sh": error=13, Permission denied`, i.e. Android 17 refuses to
exec files from the app data dir for this build, while the Play build (newer targetSdk + linker-based exec) runs fine on the same phone.
=> **Before uninstalling a working Termux, test the replacement first**: install the F-Droid build under a *different test* (e.g. on another device/
emulator) or accept that on very new Android the Play build may be the only one that runs. Do NOT uninstall the working Termux until the
replacement has booted to a shell prompt. (Here we uninstalled first; recovery = reinstall the saved Play APK splits with
`adb install-multiple` and restore the verified backup.) Try `com.termux_1022.apk` (0.119.0-beta.3, same F-Droid key) as the next candidate.

## CHECK STORAGE RIGHT BEFORE the destructive/large step (it changed by 39 GB overnight)
Free space went 42 GB -> 3.2 GB between the backup and the restore (offline videos, game data, **a ~7 GB app backup is
created nightly**). A restore needs the archive (already on the phone) + the extracted data (here 21.1 GB) = **at least ~25 GB free after
the uninstall frees the old app data, plus margin**. Re-check `adb shell df -h /sdcard` immediately before uninstalling; if tight, free
space by MOVING (never just deleting) the user's data to the PC with the verified method below, and only what the user allows.
Find what's big: `du -sk /sdcard/* | sort -rn`, `find /sdcard -xdev -type f -mmin -1200 -size +200M`.

**Verified move of a folder with non-ASCII names, over flaky adb (862 files, 26.8 GB):** build an index ON the phone
(`find . -type f | sort > list.txt`, per-file `stat -c %s` and `sha256sum` in the same order), pull the index files byte-exactly, fetch each
file by *line number* with a phone-side `get.sh <n> <skipMiB> <countMiB>` (`dd` slices, 1 GiB, `adb exec-out`, size-checked, retried, adb server
restarted when offline) so no unicode name ever passes through a command line, verify every file's SHA-256 on the PC against the phone,
then build the tree with the real names (Windows-illegal characters replaced and listed in a map), compare file count + total bytes, and only
then (with the user's OK for the move) remove the source on the phone. Keep `manifest.csv`.

## HARD LIMIT: a secure-locked phone blocks every UI step (found during the unattended migration)
`dumpsys window | grep mCurrentFocus` shows `Bouncer` (PIN/pattern prompt) or `NotificationShade` when the phone is locked.
Then `input text`/taps cannot reach Termux and Claude must NOT try to bypass the lock (never guess PINs). `Stay awake while charging`
did not prevent it (Samsung went Dozing anyway), and the Play build of Termux has no RUN_COMMAND service, so there is no screen-free way
to run commands inside Termux. Things that still work while locked: everything that runs as the adb shell user (install/uninstall APKs,
`pm grant`, `appops`, `dumpsys`, file push/pull). So before any unattended job: ask the user to unlock the phone, set a long screen timeout and keep
it unlocked, or do only shell-side work. Order migration steps so the destructive step (uninstalling Termux) is NEVER done unless the
restore can start immediately afterwards (needs an unlocked phone). Keep a rollback: save the old APK splits
(`adb shell pm path <pkg>` lists base+splits; reinstall later with `adb install-multiple`).

## Verifying the F-Droid Termux APK before installing (done)
Download from `https://f-droid.org/repo/com.termux_<versionCode>.apk` (stable 0.118.3 = versionCode 1002, ~114 MB; ask F-Droid
`https://f-droid.org/api/v1/packages/com.termux` for `suggestedVersionCode`). Compare the v1 signing cert SHA-256 with the already-installed
F-Droid Termux:API (`adb pull` its base.apk): both were `228fb2cf...` (CN=FDroid). Same key = they can work together; the Play build
uses a different key.

## RULE: everything from F-Droid, including Termux itself (never the Play Store build)
> **Superseded on Android 17:** F-Droid Termux did not start there (see the OUTCOME section above); the Play build was the only Termux that ran. Use this rule on older Android versions.
Install the **F-Droid app** first (f-droid.org), then Termux, Termux:API, Termux:GUI (and Termux:Boot if wanted) **from F-Droid**:
same signing key, automatic updates, full Termux:API. The Play Store build of Termux cannot be updated into the F-Droid build
(different signing key, Android refuses; only uninstall works, which wipes data), so get this right the first time.
**Migrating an existing Play-build Termux without losing data** (needs the user present for the taps):
1. Backup (non-destructive, official method): in Termux
   `tar -zcf /sdcard/Download/termux-backup.tar.gz -C /data/data/com.termux/files ./home ./usr`
   (includes the Debian rootfs and Claude Code login). Verify: `tar -tzf ... | wc -l`, size, `sha256sum`; copy it to the PC too (`adb pull`).
2. Uninstall the Play Termux (and any Termux add-on signed differently), install F-Droid's Termux (+ add-ons). Open it once.
3. Restore: `tar -zxf /sdcard/Download/termux-backup.tar.gz -C /data/data/com.termux/files --recursive-unlink --preserve-permissions`, restart Termux.
4. Redo the per-install bits: Shizuku popup (new Termux = new uid), battery exemption, `adbsh` still in `usr/bin`, Termux:API permissions via `pm grant`.
Keep the backup until everything is verified. Never uninstall before the backup is verified on two copies.

## CHECK FIRST: where did Termux come from? (the Play Store trap; cost us half the Termux:API features)
Run `adb shell dumpsys package com.termux | grep -E "versionName|installerPackageName"` (or Termux > About).
`versionName=googleplay.<date>` / installer `com.android.vending` = **Google Play build**. It has **no matching Termux:API**
(termux-play-store/termux-apps#29 still open); the F-Droid Termux:API app (0.53.0) next to it only half works:
`Unable to start service com.termux.api/.TermuxApiService: not found` in logcat, and `termux-api` calls hang (exit 124) or print
"Termux:API is not yet available on Google Play". **Recommend the user installs Termux + Termux:API + Termux:GUI all from F-Droid
(same signing key)**. Replacing Termux means uninstalling the Play build (wipes its data), so back up first
(`tar -zcf /sdcard/termux-backup.tar.gz -C /data/data/com.termux/files ./home ./usr`, includes the Debian rootfs) and restore after.
Never do that unattended; ask the user. Do this check BEFORE installing anything else.

**Full capability test, S24 Ultra / Android 17 (Play-build Termux + F-Droid Termux:API 0.53.0):** 38 passed, ~13 failed, all Termux:API.
- PASS: all `/sdcard` I/O, internet, wake lock, battery, volume, toast, vibrate, notifications (after exempting Termux:API from
  battery optimization), clipboard, microphone (needed one popup + Termux:API visible), Termux:GUI python lib, **all of the Shizuku/adbsh
  tests** (identity, package lists, Android/data listing, settings read/write, screenshot, screenrecord, uiautomator dump, input,
  appops, pm grant/revoke, am broadcast/start/force-stop, disable/enable app, silent `pm install -r`), Claude Code in Debian
  (`--version`, git/curl/rg, `/sdcard`, calling `adbsh` and `termux-*`, `claude -p` end-to-end, and Claude using `adbsh` by itself).
- FAIL (Play/F-Droid mismatch, no popups were involved): text-to-speech, flashlight, Wi-Fi info, sensors, location, SMS, contacts,
  call log, telephony info, camera photo. (`termux-camera-info` returned 0 cameras.)
- **Workarounds that already work through the shell bridge (counts only were checked):** SMS `content query --uri content://sms`
  (counted, not read), contacts `content://com.android.contacts/contacts` (counted), call log `content://call_log/calls` (counted), Wi-Fi `cmd wifi status`,
  sensors `dumpsys sensorservice`, location `dumpsys location`, telephony `dumpsys telephony.registry`. Use `adbsh '<cmd>'`.
- Fixes applied for Termux:API: Doze exemption (`dumpsys deviceidle whitelist +com.termux.api`), standby bucket active. CAMERA/RECORD_AUDIO
  stay "foreground" (while-in-use) at uid level and cannot be overridden: they only work while Termux:API is visible.
- Test hygiene: a test that prints nothing on success (e.g. the clipboard check) reads as FAIL; make every check print something.

## Goal
Run the real Claude Code CLI **on the phone itself** (standalone, no PC needed afterwards) with
access to phone storage (`/sdcard`), able to run dev servers (vibecoding), no root and no Shizuku.

## Why this approach (decisions already made, don't re-litigate)
- Anthropic's official Claude Code build has **no native Android/Termux binary** (upstream issue
  `anthropics/claude-code#50270`). `npm i -g` in plain Termux fails on the native binary.
- Workaround used: **Debian inside Termux via `proot-distro`**, then the **official installer**
  (`curl -fsSL https://claude.ai/install.sh | bash`) inside Debian. Debian = glibc, which is what the
  official Linux binary targets. Alpine (musl) and Ubuntu (snap/systemd assumptions) were rejected.
- No root, no Shizuku needed. Shizuku is optional (see "Optional extras").
- Alternatives considered: `ferrumclaudepilgrim/claude-code-android` (glibc-runner shim / AVF VM),
  `techjarves/Mobile-Harness`, AndCode. Avoid projects built on leaked Claude Code source
  (OpenClaude / "Claw Code" variants): provenance and licensing are doubtful.

## What the user may NOT have (check first, don't assume)
| Item | How to check / get it |
|---|---|
| Termux | **Recommend installing via the F-Droid app** (https://f-droid.org) so Termux and its add-ons (Termux:API, Termux:GUI, Termux:Boot) get **automatic updates**. GitHub releases also work but won't auto-update. Not the Play Store (outdated). **Keep all Termux apps from the same source/signature**, or installs/updates fail. |
| Developer options + USB debugging | Settings > About phone > Software information > tap *Build number* 7x, then Developer options > USB debugging. |
| A PC with adb (only needed for the *assisted* setup) | See "PC side". The phone-only path needs no PC. |
| Shizuku | Not required. |
| Claude account | Claude Pro/Max/Team/Enterprise or an Anthropic Console API key. |

Phone-specific blockers seen:
- **Samsung Auto Blocker** blocks USB commands and hides the "Allow USB debugging?" dialog. Turn it off
  (Settings > Security and privacy > Auto Blocker) if adb stays `unauthorized`.
- USB mode must be **File transfer** (not "Charging only"); data cable, not charge-only.
- `adb devices` showing `unauthorized` = approve the RSA dialog on the phone ("Always allow").
- **Locked or sleeping phone:** `adb devices` can flip to `offline`, and `adb shell` fails with
  "device offline" or "no devices/emulators found", mid-task. Windows still shows the phone and an
  "ADB Interface", so it looks like a driver problem but isn't. Fix: ask the user to **unlock the phone**
  (and approve any USB debugging prompt), then `adb reconnect offline` or `adb kill-server && adb start-server`,
  then `adb devices` until it says `device`. Never loop on retries while the phone is locked; ask the user.
  Observed: after the user unlocked the phone, `adb devices` stayed empty/`offline` until
  `adb kill-server; adb start-server` (a plain `adb reconnect` was not enough); then it showed `device`.
  **Fix that finally worked when adb stayed empty/offline/flapping (e.g. after a long heavy job on the phone, a PC restart or a USB driver change):**
  (1) phone: Developer options > *Revoke USB debugging authorizations*; (2) turn *USB debugging* off and on (or replug);
  (3) accept "Allow USB debugging?" and **tick "Always allow from this computer"**: a one-time approval is forgotten on the next
  drop, so adb keeps flapping; (4) PC: `adb kill-server; adb start-server`, wait a few seconds, `adb devices` must say `device`.
  Don't spam `adb reconnect offline` (it can knock the transport off again). Windows showing the "ADB Interface" while `adb devices`
  is empty means the problem is the phone's authorization state, not the driver.
  Prevention: Developer options > "Stay awake" (screen stays on while charging), or have the user keep it
  unlocked during setup. Check `adb devices` before every batch of adb commands in a long task.
- Other manufacturers: names differ (Xiaomi "USB debugging (Security settings)", etc.); the
  `unauthorized` / USB-mode / cable checks are universal.

## PC side (Windows) — only for the PC-assisted setup
1. Install the **Android CLI** (Google-signed):
   ```
   curl.exe -fsSL https://dl.google.com/android/cli/latest/windows_x86_64/install.cmd -o "%TEMP%\i.cmd" && "%TEMP%\i.cmd"
   ```
   It installs to `%LOCALAPPDATA%\..\AndroidCLI` (`C:\Users\<user>\AppData\AndroidCLI\android.exe`) and adds it to the *user* PATH.
2. Run **`android init`** afterwards. This sets up the CLI's config and **installs the Claude (android-cli) skill**.
   Skip this and the skill is missing.
3. **PATH gotcha:** existing terminals keep the old PATH. A new cmd window launched from a stale
   parent (Explorer/Terminal) still won't see `android`. Sign out/in (or reboot) or call it by full path.
4. **adb is not bundled.** `android screen capture` says "No online devices" even when Windows sees the
   phone, because the SDK has no platform-tools. Install them with (ask the user first):
   ```
   android sdk install platform-tools
   ```
   adb then lives at `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe`.
5. Verify: `adb devices` must list the phone as `device` (not `unauthorized`).
   `Get-PnpDevice` showing an "ADB Interface" confirms Windows sees it.

## Phone side: install Debian + Claude Code
Do it with a **script file, not typed one-liners**. Typing into Termux through `adb shell input text`
works only for short commands (spaces must be `%s`, many symbols break), so push a script to
`/sdcard/Download/` and type just `bash /sdcard/Download/cc-setup.sh`.

Driving Termux from the PC:
```
adb shell input keyevent KEYCODE_WAKEUP
adb shell monkey -p com.termux -c android.intent.category.LAUNCHER 1     # open Termux
adb push cc-setup.sh /sdcard/Download/cc-setup.sh
adb shell input text "bash%s/sdcard/Download/cc-setup.sh"; adb shell input keyevent KEYCODE_ENTER
adb shell input keycombination KEYCODE_CTRL_LEFT KEYCODE_C                # Ctrl+C in Termux
adb shell screencap -p /sdcard/Download/_s.png; adb pull /sdcard/Download/_s.png   # see the screen
```
The script `tee`s to `/sdcard/Download/cc-setup.log`, which the PC can `adb shell cat` to follow progress
(note: dpkg unpack output lags in the log; the phone screen is live).

### The script (final working form is below once verified)
(The setup script itself is not included here: it only chains the commands described in this guide: `proot-distro install debian`, then in Debian `apt-get install --no-install-recommends curl git ripgrep ca-certificates` and the official Claude Code installer.)

## Lessons / mistakes to avoid
- **`apt-get install` pulls "recommends" by default** (X11, Mesa, ...): always `--no-install-recommends`.
- **Don't install `npm` / `build-essential` up front.** Debian's `npm` drags in ~400 tiny `node-*`
  packages; unpacking under proot took ~1 package/minute. Claude Code's native installer needs
  neither Node nor a compiler. Install them later only when a project needs them.
- `-o Dpkg::Options::=--force-unsafe-io` speeds dpkg a lot under proot.
- After interrupting apt, run `dpkg --configure -a` before retrying.
- `proot-distro install debian` errors with "container already exists" on a rerun. Don't detect via a
  guessed directory (path differs between proot-distro versions); use `... || echo already installed`.
- `proot-distro list --installed` is not a reliable existence check either.
- With `set -e`, one failed detection step aborts the whole script silently into the shell prompt.

## Verified results (S24 Ultra, Android 17, Debian 13 "trixie" arm64)
- Official installer inside Debian worked: Claude Code 2.1.318 at `~/.local/bin/claude`.
  Add to PATH: `echo 'export PATH=$HOME/.local/bin:$PATH' >> ~/.bashrc`.
- `proot-distro login debian --bind /sdcard:/sdcard` shows phone storage at `/sdcard` inside Debian.
  (proot-distro 5.x already binds `/sdcard`, so the extra `--bind` only prints an "overlaps" warning. Harmless.)
- Debian rootfs size: `/usr` ~860 MB when `build-essential` + `npm` are installed (gcc/g++ ~125 MB,
  libnode ~50 MB, many `node-*` packages), `~/.local` (Claude Code binary + data) ~320 MB.
  A minimal install (curl git ripgrep ca-certificates) is far smaller.
- After removing nodejs/npm/gcc/build-essential (`apt-get purge ... && apt-get autoremove --purge`) the
  Debian container is **~696 MB** (measured via `du -sh $PREFIX/var/lib/proot-distro`): Claude Code
  binary ~323 MB (`~/.local/share/claude/versions`, not shrinkable), `/usr` ~317 MB
  (locale 45, perl 23+libperl 31, python 29+10, docs 19, man 8). Freed ~550 MB by the purge.
  Claude Code can install Node/gcc itself later when a project needs them.
- Optional further strip (~70-110 MB): delete `/usr/share/{locale,doc,man,info}`, purge python3. Perl stays (git needs it).
- Cleanup after install (phone storage is often tight): `apt-get clean && rm -rf /var/lib/apt/lists/*`
  inside Debian, and delete the helper scripts/logs from `/sdcard/Download`.

## RULE: look at the phone screen right before every `input text`
`adb shell input text` types into **whatever is in the foreground**. After the user logs in, Termux is
often sitting inside a running **Claude Code** session (or an editor, `less`, a password prompt...).
Typing a shell command there sends it to Claude Code as a *prompt*, which then "helpfully" runs it itself
(this happened: it executed `cc-api.sh` and the run was interrupted). So, every single time, immediately
before typing: take a screenshot, confirm a plain shell prompt (`~ $`), and if something else is open
ask the user to exit it (or press Ctrl+C / `/exit` yourself only if they agree). Never batch
"launch Termux + type" without a screenshot in between. Also avoid typing while the user is using the phone.
Preferable alternative once the user is logged in: let the *phone's* Claude Code run the setup steps itself.

## More lessons
- **`adb shell input text` and `;` / `&` / `|`**: the *phone's* shell interprets them, so
  `input text "clear;bash%s..."` runs `bash...` as a shell command on the phone instead of typing it.
  Type one simple command at a time; use `%s` for spaces.
- Ctrl+C via `adb shell input keycombination KEYCODE_CTRL_LEFT KEYCODE_C` needs Android 12+ and did
  **not** reliably stop a running apt in Termux: an "interrupted" run may still finish. Check the screen
  before assuming it stopped, and don't start a second install on top of it.
- Termux's own display is the source of truth for progress; `tee` logs lag behind.
- Screenshots of the phone: take them to a temp folder, delete them afterwards.

## Launcher + battery (done, verified)
- `cc` command in Termux's `~/.bashrc` (works: `cc --version` printed 2.1.318):
  ```
  cc() { termux-wake-lock; proot-distro login debian -- /root/.local/bin/claude "$@"; termux-wake-unlock; }
  ```
  The wake lock is held only while Claude runs (limits battery use). Reload with `exec bash` or a new session.
- Termux-only battery exemption from the PC: `adb shell dumpsys deviceidle whitelist +com.termux`
  (reverse: `-com.termux`). Does not affect other apps.

## Termux:API and Termux:GUI (verified)
- Android apps `com.termux.api` and `com.termux.gui` (from F-Droid) + Termux packages inside Termux:
  `pkg install -y termux-api termux-gui-package` (installs the `termuxgui` Python lib).
- **Works inside Debian too**: proot passes Termux's `bin` dir on `PATH`
  (`/data/data/com.termux/files/usr/bin`), so `termux-battery-status`, `termux-clipboard-get`,
  `termux-notification`... run from Claude Code in Debian. Verified with `termux-battery-status`.
- Features needing Android runtime permissions (camera, location, SMS, contacts, microphone) are **not**
  granted by default; grant only what the user wants, and ask first.
- Claude Code in Debian prints "Cross-session messaging is off ... user namespace without a uid mapping".
  Harmless for normal use.

## Shell-level access: Shizuku + rish (optional, only where truly needed)
What it adds: commands run as the Android `shell` user from Termux/Debian (`pm install`, `pm grant`,
`settings`, `input`, `screencap`, `am`, `dumpsys`, reading `/sdcard/Android/data`). Not needed for
normal Claude Code use. Without Shizuku, installing an APK from Termux = `termux-open app.apk` + user taps Install.

**Start the Shizuku service from the PC over USB (no Wi-Fi pairing needed, redo after every reboot):**
```
BASE=$(adb shell pm path moe.shizuku.privileged.api | sed 's/package://; s#/base.apk##')
adb shell "$BASE/lib/arm64/libshizuku.so"      # starter; prints "shizuku_server pid is ..."
adb shell ps -A | grep shizuku_server           # verify
```
**Install rish into Termux** (files ship inside the Shizuku APK: `assets/rish`, `assets/rish_shizuku.dex`):
1. `adb pull` the APK (path from `pm path`), extract those two assets, push to `/sdcard/Download/`.
2. In Termux: copy to `~/.rish/`, `chmod 400 rish_shizuku.dex` (Android 14+ refuses a writable dex),
   `sed` the script to `export RISH_APPLICATION_ID=com.termux`, `chmod 700 rish`.
3. **Run it as `sh ~/.rish/rish -c 'id'`**, not by exec'ing the script directly: executing it directly gave
   `unable to open file "/system/bin/sh"` (Termux exec shim / shebang). `sh rish` reached Shizuku.
4. First call triggers a **"Allow Termux to access Shizuku?" popup on the phone**: only the user may tap
   "Allow all the time". It times out after ~30 s if unanswered ("Request timeout ... battery optimization"
   is misleading: the usual cause is nobody tapped, or the popup isn't visible). Warn the user first,
   use `timeout 150`, and take a screenshot to see whether the dialog is showing.
   **A tap on a stale/expired popup does NOT grant anything.** Verify in the Shizuku app (open it with
   `adb shell monkey -p moe.shizuku.privileged.api -c android.intent.category.LAUNCHER 1`, screenshot): the card
   must say "Authorized 1 applications". If it says 0, start a fresh `rish` request, tell the user to tap *Allow all the time*
   while it is waiting (it hangs silently until answered or `timeout` kills it, exit 124), then re-check.
   Ask the user to be ready *before* you trigger the popup.
   **Timing (observed):** the popup appears ~3-5 s after `rish` starts and the request dies after roughly 30 s with
   "Request timeout ... battery optimization" (a misleading message: it just means nobody tapped in time). The user must
   be looking at the phone before you trigger it. When the Shizuku service was started from the Shizuku app itself
   (Wireless debugging, "adb" mode) the popup showed reliably; after my adb-started service it often did not.
5. The error "Server is not running" right after changing battery settings = the Shizuku *app* process had
   just restarted; retry. Exempting the Shizuku app from Doze (`adb shell dumpsys deviceidle whitelist +moe.shizuku.privileged.api`)
   is app-specific and reversible (`-`).
- If a dialog is covering Termux, do NOT type; the user must answer it first.

## FINAL `adbsh` WRAPPER (supersedes the FIFO wrapper further below): fixes the "truncated output"
**Root cause found:** not rish. (1) `rish` only returns output reliably with stdin handled right, and (2) Android's package
service itself fails with `cmd: Failure calling service package: Failed transaction` when the command's stdout is a **file on
/sdcard** (FUSE), which looked like random truncation (247/218 of 465 lines). Running the command into a **pipe** and letting
`cat` write the file fixed it: 10/10 runs gave 465 packages, 6/6 gave 967, exit codes and quoting correct, works from Debian.
```bash
#!/data/data/com.termux/files/usr/bin/bash          # $PREFIX/bin/adbsh   usage: adbsh pm list packages -3
R=/data/data/com.termux/files/home/.rish/rish; D=/sdcard/.adbsh; mkdir -p "$D"
once() {
  id="$$.$RANDOM"; C="$D/c.$id"; O="$D/o.$id"; X="$D/x.$id"; printf '%s\n' "$*" > "$C"
  launch() { f=$(mktemp -u "${TMPDIR:-/tmp}/adbsh.XXXXXX"); mkfifo "$f"; sleep 30 > "$f" & sp=$!
    timeout 40 sh "$R" -c "setsid sh -c '( sh $C 2>&1 < /dev/null; echo \$? > $X.t ) | cat > $O; mv $X.t $X' > /dev/null 2>&1 < /dev/null &" < "$f" > /dev/null 2>&1
    kill "$sp" 2>/dev/null; rm -f "$f"; }
  launch
  for t in 1 2 3; do { [ -e "$O" ] || [ -e "$X" ]; } && break; sleep 2; { [ -e "$O" ] || [ -e "$X" ]; } || launch; done   # cold start
  i=0; while [ ! -e "$X" ] && [ $i -lt $((${ADBSH_TIMEOUT:-60}*5)) ]; do sleep 0.2; i=$((i+1)); done
  RES=$(cat "$O" 2>/dev/null); RC=$(cat "$X" 2>/dev/null); rm -f "$C" "$O" "$X"; }
for try in 1 2 3; do once "$@"; printf '%s' "$RES" | grep -qE 'Failure calling service|Failed transaction' || break; sleep 1; done
[ -n "$RES" ] && printf '%s\n' "$RES"; exit ${RC:-124}
```
Never redirect a system-service command's stdout to /sdcard directly; use a pipe.

## Permissions granted to Termux:API (done over adb with `pm grant`; the user asked for max access)
CAMERA, RECORD_AUDIO, ACCESS_FINE/COARSE/BACKGROUND_LOCATION, READ_SMS, SEND_SMS, READ_CONTACTS, READ_CALL_LOG, CALL_PHONE,
READ_PHONE_STATE, POST_NOTIFICATIONS, READ_MEDIA_IMAGES/VIDEO/AUDIO/VISUAL_USER_SELECTED, ACCESS_MEDIA_LOCATION, BODY_SENSORS,
READ/WRITE_EXTERNAL_STORAGE. Special access via `appops set <pkg> <OP> allow`: MANAGE_EXTERNAL_STORAGE (termux, termux.api),
REQUEST_INSTALL_PACKAGES (termux), WRITE_SETTINGS (termux.api). Deliberately **not** granted (more invasive; only on request):
notification listener, usage access, draw-over-apps. `pm grant` prints nothing on success. Ask the user first in real setups.

## FINAL WORKING RECIPE: Shizuku + rish (PC-free after reboot; verified on S24 Ultra, Android 17)
What finally worked: **start Shizuku from its own app** (Shizuku app > "Start via Wireless debugging": needs Wi-Fi,
Developer options > Wireless debugging on, pair once), then install `rish` into Termux as described below, run the
first `rish` call so the user can tap **Allow all the time** on the popup (tap within ~30 s), and from then on
`sh ~/.rish/rish -c id` returned `uid=2000(shell)`. After a reboot the user restarts Shizuku in its app (Wi-Fi needed, no PC).
Key gotchas learned:
- **rish gives no output unless its stdin is handled right.** Inherited tty + redirected stdout = empty. `</dev/null` mostly
  works but can cut long output (EOF ends the remote command early). Reliable: keep stdin open on a FIFO until rish exits.
- Wrapper `adbsh` (in `$PREFIX/bin`, also callable from Debian because Termux's bin is on PATH there):
  ```
  #!/data/data/com.termux/files/usr/bin/bash
  R=/data/data/com.termux/files/home/.rish/rish
  run() { f=$(mktemp -u "${TMPDIR:-/tmp}/adbsh.XXXXXX"); mkfifo "$f"; sleep 120 > "$f" & sp=$!
          timeout 60 sh "$R" -c "$*" < "$f" 2>/dev/null; kill "$sp" 2>/dev/null; rm -f "$f"; }
  out=$(run "$@"); [ -z "$out" ] && { sleep 1; out=$(run "$@"); }; [ -n "$out" ] && printf '%s\n' "$out"; exit 0
  ```
  Usage: `adbsh pm list packages -3`, `adbsh settings get global adb_wifi_enabled`. Verified from Termux and from Debian.
- Remaining flakiness: the first calls after idle can return truncated long output (saw 247 of 465 lines twice, then 465).
  For anything important, check the result count / rerun. `id`, `settings get` were reliable.
- Starting Wireless debugging leaves it ON (`adb_wifi_enabled=1`). Tell the user; they can turn it off after Shizuku is
  running (Shizuku keeps running until reboot).
- Test scripts that redirect output to a file hung when Shizuku was not yet authorized, which looked identical to an
  rish bug. Do the first authorization interactively (user watching, command typed directly in the terminal).

## Shell-level access: on-phone adb bridge (verified; BUT needs a PC after every reboot)
> The user rejected this as the final solution because it needs a PC after each reboot (`adb tcpip 5555`).
> A PC-free variant exists (Wireless debugging + one-time pairing + Termux:Boot; needs Wi-Fi at boot, and
> Android may reset the toggle on reboot, so a helper with WRITE_SECURE_SETTINGS might be needed). Ask in the
> upfront questions whether a PC-needed-after-reboot bridge is acceptable.
> **Undo:** `adb usb` from the PC closes the TCP port (verified: port 5555 stops listening). Side effect:
> restarting adbd also killed the adb-started `shizuku_server`, so Shizuku must be started again afterwards.
On the S24 Ultra / Android 17, Shizuku started fine but `rish` hung silently with no usable popup
(app showed "Authorized 0"). The adb bridge gave the same power reliably, so **prefer this**; only use Shizuku
if some other app specifically needs the Shizuku API.
1. PC, phone plugged in and unlocked: `adb tcpip 5555` (phone's adbd also listens on TCP). Redo after every reboot.
2. Termux: `pkg install -y android-tools`, then `adb start-server; adb connect localhost:5555`.
   First connect says `failed to authenticate`; the phone shows **"Allow USB debugging?"**: the user ticks
   *Always allow* and taps Allow (only the user can). Reconnect in a loop until `adb devices` shows `localhost:5555 device`.
3. Use it: `adb -s localhost:5555 shell '<cmd>'` runs as `uid=2000(shell)`: `pm install`, `pm grant`, `settings`,
   `input`, `screencap`, `am`, `dumpsys`, reading `/sdcard/Android/data`. (`adb devices` may also list the same phone as `emulator-5554`.)
4. Limits: Samsung Secure Folder / other user profiles (user 150) give `SecurityException`; works only after step 1 each boot.
5. Install an APK silently: `adb -s localhost:5555 install -r /sdcard/Download/app.apk`.
Without any of this, an APK can still be installed with `termux-open app.apk` and the user taps Install.

## Login (user does this themselves; never enter their credentials)
1. In Termux run `cc`. Pick the login method (Claude account or Console/API key).
2. It prints a URL: open it in the phone browser, approve, copy the code, paste it back into Termux.
3. Start in a project folder, e.g. `cd /sdcard/<project>` inside Debian before `claude`
   (or `proot-distro login debian` and then `cd`).

## Not yet done / TODO in this guide
- [x] Confirm install finishes and `claude --version` works (done, 2.1.318)
- [ ] Login flow (OAuth link opened in phone browser, paste code back)
- [x] Storage: `/sdcard` visible inside Debian (verified)
- [x] Cleanup of temp files / apt cache on the phone (done)
- [ ] Decide whether to trim `build-essential`/npm to save space (asked user)
- [ ] Optional: phantom-process (Android 12+) setting. Deliberately **not** applied: it is global (all apps),
      only matters if long sessions get killed. Termux-only mitigations: `termux-wake-lock`, disable battery
      optimization for Termux.
- [ ] Optional extras: Termux:API, `adb tcpip 5555` for on-phone adb, sshd bridge
- [ ] Final cleanup pass over this document
