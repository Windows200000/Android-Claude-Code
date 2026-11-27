#!/usr/bin/env python3
"""killwatch: a flight recorder for "what keeps killing my Termux session?".

  killwatch.py start     run in the background: sample memory / processes every 2 s, follow Android's kill messages (needs adb)
  killwatch.py stop
  killwatch.py status
  killwatch.py report    after a kill: the last seconds before it, kill events from Android's log, relevant settings, a verdict

Logs go to /sdcard/Download/killwatch/ so they survive the session dying. Stdlib only, light on CPU.
"""
import os, re, sys, time, json, subprocess, threading, signal, socket, concurrent.futures as cf

OUT = '/sdcard/Download/killwatch'
SAMPLES, EVENTS, PIDF = OUT + '/samples.log', OUT + '/events.log', OUT + '/pid'
LAST_ADB = '/data/data/com.termux/files/home/.adbself_last'
INTERVAL = 2.0
KILL_RE = re.compile(r'lmkd|Killing |am_kill|am_proc_died|PhantomProcessList|phantom|excessive|SIGKILL|signal 9|low memory|lowmemory|OomAdjuster|ProcessRecord.*(kill|died)|termux', re.I)
os.makedirs(OUT, exist_ok=True)

def now(): return time.strftime('%H:%M:%S')

# ---------------------------------------------------------------- logging that survives a kill
def append(path, line):
    with open(path, 'a') as f:
        f.write(line + '\n'); f.flush(); os.fsync(f.fileno())
    try:
        if os.path.getsize(path) > 6 * 1024 * 1024:                      # keep the newest ~2 MB
            data = open(path, 'rb').read()[-2 * 1024 * 1024:]
            open(path, 'wb').write(data[data.find(b'\n') + 1:])
    except OSError: pass

# ---------------------------------------------------------------- adb (optional, gives the real kill reason)
adb_dev = None
def adb(*args, timeout=8):
    try:
        return subprocess.run(['adb'] + list(args), capture_output=True, text=True, timeout=timeout, env=dict(os.environ, TMPDIR='/tmp')).stdout
    except Exception: return ''

def adb_connect():
    global adb_dev
    out = adb('devices')
    for l in out.splitlines()[1:]:
        p = l.split()
        if len(p) == 2 and p[1] == 'device': adb_dev = p[0]; return True
    try:                                                         # last known address first
        last = open(LAST_ADB).read().strip()
        if last and 'connected' in adb('connect', last, timeout=6): adb_dev = last; return True
    except Exception: pass
    if not out:                                                  # no server yet: start one that outlives this call
        subprocess.Popen(['setsid', 'nohup', 'adb', '-L', 'tcp:5037', 'nodaemon', 'server'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=dict(os.environ, TMPDIR='/tmp'))
        time.sleep(3)
    def probe(p):
        s = socket.socket(); s.settimeout(0.4)
        try: s.connect(('127.0.0.1', p)); return p
        except Exception: return None
        finally: s.close()
    with cf.ThreadPoolExecutor(40) as ex:
        ports = [p for p in ex.map(probe, range(30000, 60001)) if p]
    for p in ports:
        if 'connected' in adb('connect', f'127.0.0.1:{p}', timeout=5):
            for l in adb('devices').splitlines()[1:]:
                q = l.split()
                if len(q) == 2 and q[1] == 'device': adb_dev = q[0]; return True
    return False

def adb_shell(cmd, timeout=8):
    return adb('-s', adb_dev, 'shell', cmd, timeout=timeout) if adb_dev else ''

# ---------------------------------------------------------------- sampling
GROUPS = {'claude': re.compile(r'(^|/)claude( |$)|claude-code'), 'firefox': re.compile(r'firefox'), 'chromium': re.compile(r'chromium'),
          'ffmpeg': re.compile(r'ffmpeg'), 'java': re.compile(r'(^|/)java( |$)'), 'adb': re.compile(r'(^|/)adb( |$)'), 'python': re.compile(r'python3?( |$)')}

def meminfo():
    d = {}
    for l in open('/proc/meminfo'):
        k, v = l.split(':'); d[k] = int(v.split()[0]) // 1024
    return d

def procs():
    out = []
    for p in os.listdir('/proc'):
        if not p.isdigit(): continue
        try:
            st = open(f'/proc/{p}/status').read()
            name = re.search(r'Name:\s+(\S+)', st).group(1)
            ppid = int(re.search(r'PPid:\s+(\d+)', st).group(1))
            m = re.search(r'VmRSS:\s+(\d+)', st); rss = int(m.group(1)) // 1024 if m else 0
            cmd = open(f'/proc/{p}/cmdline', 'rb').read().replace(b'\0', b' ').decode('utf8', 'ignore')[:90]
            out.append((int(p), ppid, name, rss, cmd))
        except Exception: pass
    return out

termux_uid = None
def adb_sample():
    """what Android thinks of the Termux app: importance (oom_score_adj), RSS, how many processes it owns"""
    global termux_uid
    if not adb_dev: return None
    if termux_uid is None:
        m = re.search(r'\s(u0_a\d+)\s', adb_shell('ls -ld /data/data/com.termux 2>/dev/null; ls -ldn /data/data/com.termux 2>/dev/null'))
        termux_uid = m.group(1) if m else ''
    s = adb_shell('p=$(pidof com.termux | cut -d" " -f1); [ -n "$p" ] && echo "pid=$p adj=$(cat /proc/$p/oom_score_adj) $(grep -E "VmRSS|Threads" /proc/$p/status | tr -s " \\t" " " | tr "\\n" " ")"; ps -A -o USER 2>/dev/null | grep -c "^' + termux_uid + '$"') if termux_uid else adb_shell('pidof com.termux')
    return ' '.join(s.split())[:160]

def sample(n):
    mi = meminfo(); pr = procs()
    g = {}
    for k, rx in GROUPS.items():
        hits = [x for x in pr if rx.search(x[4]) or rx.search(x[2])]
        if hits: g[k] = [len(hits), sum(x[3] for x in hits)]
    top = sorted(pr, key=lambda x: -x[3])[:3]
    rec = {'t': now(), 'anc': chain_state(), 'avail': mi.get('MemAvailable'), 'free': mi.get('MemFree'), 'swapfree': mi.get('SwapFree'), 'nproc': len(pr),
           'g': g, 'top': [[x[2], x[3]] for x in top], 'load': os.getloadavg()[0]}
    if n % 5 == 0:
        a = adb_sample()
        if a: rec['android'] = a
    append(SAMPLES, json.dumps(rec, separators=(',', ':')))

def follow_log():
    while True:
        if not adb_dev: adb_connect()
        if adb_dev:
            try:
                p = subprocess.Popen(['adb', '-s', adb_dev, 'logcat', '-b', 'main', '-b', 'system', '-b', 'events', '-v', 'epoch', '-T', '1'],
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=dict(os.environ, TMPDIR='/tmp'))
                for line in p.stdout:
                    if KILL_RE.search(line) and 'killwatch' not in line: append(EVENTS, f'{now()} {line.strip()[:400]}')
            except Exception: pass
            globals()['adb_dev'] = None
        time.sleep(15 if adb_dev else 60)        # an unanswered port scan is expensive: try once a minute

def ancestors(pid):
    chain = []
    while pid > 1 and len(chain) < 12:
        try:
            st = open(f'/proc/{pid}/status').read()
            chain.append([pid, re.search(r'Name:\s+(\S+)', st).group(1)]); pid = int(re.search(r'PPid:\s+(\d+)', st).group(1))
        except Exception: break
    return chain

CHAIN = []
def chain_state():
    return ''.join('1' if os.path.exists(f'/proc/{p}') else '0' for p, _ in CHAIN)

def run():
    global CHAIN
    try: CHAIN = json.loads(os.environ.get('KW_CHAIN', '[]'))
    except Exception: CHAIN = []
    open(PIDF, 'w').write(str(os.getpid()))
    append(SAMPLES, json.dumps({'t': now(), 'chain': CHAIN}, separators=(',', ':')))
    append(SAMPLES, json.dumps({'t': now(), 'event': 'killwatch started', 'pid': os.getpid()}))
    threading.Thread(target=follow_log, daemon=True).start()
    n = 0
    while True:
        try: sample(n)
        except Exception as e: append(SAMPLES, json.dumps({'t': now(), 'error': str(e)[:100]}))
        n += 1; time.sleep(INTERVAL)

# ---------------------------------------------------------------- commands
def alive():
    try: pid = int(open(PIDF).read()); os.kill(pid, 0); return pid
    except Exception: return None

def report():
    print('=== killwatch report ===')
    try: lines = [json.loads(l) for l in open(SAMPLES).read().splitlines()[-400:] if l.startswith('{')]
    except Exception: print('no samples yet'); return
    starts = [i for i, r in enumerate(lines) if r.get('event') == 'killwatch started']
    print(f"samples: {len(lines)}; last recorded at {lines[-1]['t']}; the recorder itself {'is running' if alive() else 'is NOT running (it died with the session, or was never started)'}")
    if starts and starts[-1] > 0: print(f"recorder (re)started at {lines[starts[-1]]['t']}: the run before it ended at {lines[starts[-1]-1]['t']}  <- when the previous session died")
    seg = lines[starts[-1] - 25:starts[-1]] if starts and starts[-1] >= 5 else lines[-25:]
    chains = [r for r in lines if 'chain' in r]
    if chains:
        ch = chains[-1]['chain']; print('processes above the session that started the recorder (child -> parent):', ' <- '.join(f'{n}[{p}]' for p, n in ch))
        trans = [(r['t'], r['anc']) for r in lines if 'anc' in r]
        died = [(t, a) for (t, a), (_, b) in zip(trans[1:], trans[:-1]) if a != b]
        if died: print('  those parents changed state at:', ', '.join(f'{t} ({a})' for t, a in died[:6]), ' (1 = alive, 0 = gone, in the order listed above)')
    print('\nthe last samples before the end of that run (avail MB / swap free MB / procs / groups [count,MB] / top):')
    for r in seg:
        if 'avail' in r: print(f"  {r['t']}  anc {r.get('anc','')}  avail {r['avail']:5}  swap {r['swapfree']:5}  procs {r['nproc']:3}  {r.get('g')}  top {r.get('top')}  {r.get('android','')}")
    print('\nkill-related lines from Android\'s log captured by the recorder (last 15):')
    try:
        ev = open(EVENTS).read().splitlines()[-15:]
        print('\n'.join('  ' + e[:230] for e in ev) if ev else '  (none captured)')
    except Exception: print('  (none captured)')
    if adb_connect():
        print('\nfrom Android\'s log history right now (kills mentioning termux / lmkd / phantom; newest last):')
        out = adb('-s', adb_dev, 'logcat', '-d', '-b', 'all', '-v', 'time', '-t', '8000', timeout=40)
        hits = [l for l in out.splitlines() if re.search(r'lmkd.*(kill|Kill)|Killing .*termux|termux.*(kill|died)|PhantomProcessList|phantom|am_kill.*termux|am_proc_died.*termux|excessive', l, re.I)][-15:]
        print('\n'.join('  ' + h[:230] for h in hits) if hits else '  (nothing about termux/lmkd/phantom in the retained log)')
        print('\nsettings that decide how aggressively Android kills background child processes:')
        print('  max_phantom_processes (default 32):', adb_shell('device_config get activity_manager max_phantom_processes').strip() or 'unset')
        print('  settings_enable_monitor_phantom_procs:', adb_shell('settings get global settings_enable_monitor_phantom_procs').strip() or 'unset')
    else:
        print('\n(no adb connection: switch Wireless debugging on to also read Android\'s own kill log)')
    low = [r for r in seg if 'avail' in r and r['avail'] is not None and r['avail'] < 600]
    fxmax = max([r.get('g', {}).get('firefox', [0])[0] for r in seg if 'avail' in r] or [0])
    nprocmax = max([r['nproc'] for r in seg if 'avail' in r] or [0])
    print('\nverdict hints:')
    print(f"  - memory: {'LOW (<600 MB available) in the last samples -> Android low-memory killer is likely' if low else 'was not critically low just before the end'}")
    print(f"  - process count peaked at {nprocmax}; Firefox processes at most {fxmax}  ({'many child processes -> the phantom process cap (32) is a prime suspect' if nprocmax > 40 or fxmax > 10 else 'not unusual'})")

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if cmd == 'run': run()
    elif cmd == 'start':
        if alive(): print('already running, pid', alive()); return
        ch = ancestors(os.getpid()); i = next((k for k, (_, n) in enumerate(ch) if 'claude' in n), 0)      # start at the Claude process: the shell of this very command is short-lived
        env = dict(os.environ, KW_CHAIN=json.dumps(ch[i:]))
        subprocess.Popen(['setsid', 'nohup', sys.executable, '-I', os.path.abspath(__file__), 'run'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, env=env)
        time.sleep(2); print('started, pid', alive(), '- logs in', OUT)
    elif cmd == 'stop':
        p = alive()
        if p: os.kill(p, signal.SIGTERM); print('stopped', p)
        else: print('not running')
    elif cmd == 'status':
        p = alive(); print('running, pid %s' % p if p else 'not running')
        try: print(open(SAMPLES).read().splitlines()[-1][:300])
        except Exception: pass
    elif cmd == 'report': report()
    else: print(__doc__)

if __name__ == '__main__': main()
