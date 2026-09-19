import base64, hashlib, json, os, secrets, sqlite3, subprocess, threading, time, smtplib, ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from email.message import EmailMessage
from functools import wraps
from flask import Flask, jsonify, render_template, request, redirect, session, url_for
from cryptography.fernet import Fernet, InvalidToken
import yaml
from cluster_validation import validate_cluster
from vrrp_events import classify_vrrp_event, is_vrrp_health_event

app=Flask(__name__)
app.secret_key=os.getenv('SECRET_KEY') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','false').lower()=='true')
CONFIG_FILE=os.getenv('CONFIG_FILE','/app/config/config.yml'); DB='/app/data/history.db'; SETTINGS_FILE='/app/data/settings.json'
lock=threading.Lock(); notification_lock=threading.Lock(); settings_lock=threading.Lock(); availability_lock=threading.Lock(); cache={'nodes':{},'vrrp':[],'cluster':{'status':'UNKNOWN','message':'Noch keine Daten'},'updated':None}
def cfg():
    with open(CONFIG_FILE,encoding='utf-8') as f:return yaml.safe_load(f) or {}
def db_init():
    os.makedirs(os.path.dirname(DB),exist_ok=True)
    with sqlite3.connect(DB) as c:
        c.execute('CREATE TABLE IF NOT EXISTS state (name TEXT PRIMARY KEY, master TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, name TEXT, old_master TEXT, new_master TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS node_alert_state (name TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0, is_down INTEGER NOT NULL DEFAULT 0, down_since TEXT, last_alert TEXT, last_recovery TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS notification_history (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, type TEXT NOT NULL, node TEXT, ok INTEGER NOT NULL, error TEXT)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_notification_history_id ON notification_history(id DESC)')
        c.execute('CREATE TABLE IF NOT EXISTS availability_state (name TEXT PRIMARY KEY, started_at TEXT NOT NULL, last_ts TEXT NOT NULL, last_online INTEGER NOT NULL, last_maintenance INTEGER NOT NULL DEFAULT 0, monitored_seconds REAL NOT NULL DEFAULT 0, online_seconds REAL NOT NULL DEFAULT 0, outages INTEGER NOT NULL DEFAULT 0, current_down_since TEXT, last_down_start TEXT, last_down_end TEXT)')
def record_notification(kind,node,ok,error=None,ts=None):
    safe_error=str(error or '').strip()[:500] or None
    with sqlite3.connect(DB) as c:c.execute('INSERT INTO notification_history(ts,type,node,ok,error) VALUES(?,?,?,?,?)',(ts or datetime.now().isoformat(timespec='seconds'),kind,node,1 if ok else 0,safe_error))
def record_availability(nodes):
    now=datetime.now();now_s=now.isoformat(timespec='seconds');max_gap=max(15,int(cfg().get('refresh_seconds',5))*3)
    with availability_lock,sqlite3.connect(DB) as c:
        for name,node in nodes.items():
            online=1 if node.get('online') else 0;maintenance=1 if node.get('maintenance',{}).get('active') else 0
            r=c.execute('SELECT started_at,last_ts,last_online,last_maintenance,monitored_seconds,online_seconds,outages,current_down_since,last_down_start,last_down_end FROM availability_state WHERE name=?',(name,)).fetchone()
            if r is None:
                down=now_s if not online and not maintenance else None
                c.execute('INSERT INTO availability_state(name,started_at,last_ts,last_online,last_maintenance,monitored_seconds,online_seconds,outages,current_down_since,last_down_start,last_down_end) VALUES(?,?,?,?,?,0,0,?,?,?,?)',(name,now_s,now_s,online,maintenance,1 if down else 0,down,down,None));continue
            started,last_ts,last_online,last_maintenance,monitored,online_sec,outages,current_down,last_down_start,last_down_end=r
            try:elapsed=max(0,min((now-datetime.fromisoformat(last_ts)).total_seconds(),max_gap))
            except Exception:elapsed=0
            if not last_maintenance:
                monitored+=elapsed
                if last_online:online_sec+=elapsed
            if maintenance:current_down=None
            elif not online:
                if current_down is None and (last_online or last_maintenance):outages+=1;current_down=now_s;last_down_start=now_s
            elif current_down and last_online:last_down_end=now_s;current_down=None
            c.execute('UPDATE availability_state SET last_ts=?,last_online=?,last_maintenance=?,monitored_seconds=?,online_seconds=?,outages=?,current_down_since=?,last_down_start=?,last_down_end=? WHERE name=?',(now_s,online,maintenance,monitored,online_sec,outages,current_down,last_down_start,last_down_end,name))
def availability_stats():
    result=[]
    with sqlite3.connect(DB) as c:rows=c.execute('SELECT name,started_at,last_ts,last_online,last_maintenance,monitored_seconds,online_seconds,outages,current_down_since,last_down_start,last_down_end FROM availability_state ORDER BY name').fetchall()
    for r in rows:
        name,started,last_ts,last_online,last_maintenance,monitored,online_sec,outages,current_down,last_down_start,last_down_end=r;monitored=float(monitored or 0);online_sec=float(online_sec or 0);downtime=max(0,monitored-online_sec);pct=(online_sec/monitored*100) if monitored>0 else None
        result.append({'name':name,'started_at':started,'last_ts':last_ts,'online':bool(last_online),'maintenance':bool(last_maintenance),'monitored_seconds':round(monitored),'online_seconds':round(online_sec),'downtime_seconds':round(downtime),'availability':round(pct,3) if pct is not None else None,'outages':int(outages or 0),'current_down_since':current_down,'last_down_start':last_down_start,'last_down_end':last_down_end})
    return result
def fernet():return Fernet(base64.urlsafe_b64encode(hashlib.sha256(str(app.secret_key).encode()).digest()))
def env_bool(n,d=False):return os.getenv(n,str(d)).lower() in {'1','true','yes','on'}
def defaults():
    n = (cfg().get('notifications', {}).get('node_down', {}) or {})

    return {
        'notifications_enabled': True,
        'mail_enabled': env_bool('MAIL_ENABLED'),
        'node_down': bool(n.get('enabled', True)),
        'recovery_mail': bool(n.get('recovery_mail', True)),
        'vrrp_failover': True,
        'vrrp_health': True,
        'failures_before_alert': max(
            1,
            int(n.get('failures_before_alert', 3))
        ),
        'smtp_host': os.getenv('SMTP_HOST', ''),
        'smtp_port': int(os.getenv('SMTP_PORT', '587')),
        'smtp_security': os.getenv(
            'SMTP_SECURITY',
            'starttls'
        ).lower(),
        'smtp_username': os.getenv('SMTP_USERNAME', ''),
        'smtp_password_enc': '',
        'mail_from': os.getenv('MAIL_FROM', ''),
        'mail_to': os.getenv('MAIL_TO', ''),
        'last_test': None,
        'last_test_ok': None,
        'telegram_enabled': False,
        'telegram_bot_token_enc': '',
        'telegram_chat_id': '',
        'telegram_last_test': None,
        'telegram_last_test_ok': None,
        'maintenance_nodes': {},
    }

def load_settings():
    s=defaults()
    with settings_lock:
        try:
            with open(SETTINGS_FILE,encoding='utf-8') as f:s.update(json.load(f))
        except FileNotFoundError:pass
        except Exception as e:print('settings load error',e,flush=True)
    if not isinstance(s.get('maintenance_nodes'),dict):s['maintenance_nodes']={}
    return s
def save_settings(s):
    os.makedirs(os.path.dirname(SETTINGS_FILE),exist_ok=True);tmp=SETTINGS_FILE+'.tmp'
    with settings_lock:
        with open(tmp,'w',encoding='utf-8') as f:json.dump(s,f,ensure_ascii=False,indent=2)
        os.chmod(tmp,0o600);os.replace(tmp,SETTINGS_FILE);os.chmod(SETTINGS_FILE,0o600)
def maintenance_info(name):
    m=load_settings().get('maintenance_nodes',{}).get(name);return {'active':bool(m),'since':m.get('since') if isinstance(m,dict) else None}
def set_maintenance(name,active):
    s=load_settings();m=s.setdefault('maintenance_nodes',{})
    if active:m[name]={'since':datetime.now().isoformat(timespec='seconds')}
    else:m.pop(name,None)
    save_settings(s)
    if active:
        with sqlite3.connect(DB) as c:c.execute('INSERT INTO node_alert_state(name,failures,is_down) VALUES(?,0,0) ON CONFLICT(name) DO UPDATE SET failures=0,is_down=0,down_since=NULL',(name,))
def smtp_password(s):
    if s.get('smtp_password_enc'):
        try:return fernet().decrypt(s['smtp_password_enc'].encode()).decode()
        except InvalidToken:raise RuntimeError('SMTP-Passwort kann nicht entschlüsselt werden. Bitte neu eingeben.')
    return os.getenv('SMTP_PASSWORD','')
def telegram_bot_token(s):
    if s.get('telegram_bot_token_enc'):
        try:
            return fernet().decrypt(
                s['telegram_bot_token_enc'].encode()
            ).decode()
        except InvalidToken:
            raise RuntimeError(
                'Telegram Bot-Token kann nicht entschlüsselt werden. Bitte neu eingeben.'
            )
    return ''
def public_settings():
    s = load_settings()

    public = {
        k: v
        for k, v in s.items()
        if k not in {
            'smtp_password_enc',
            'telegram_bot_token_enc',
            'maintenance_nodes',
        }
    }

    public['smtp_password_set'] = bool(
        s.get('smtp_password_enc') or os.getenv('SMTP_PASSWORD', '')
    )

    public['telegram_bot_token_set'] = bool(
        s.get('telegram_bot_token_enc')
    )

    return public
def mail_enabled():return bool(load_settings().get('mail_enabled'))
def send_mail(subject,body):
    s=load_settings()
    if not s.get('mail_enabled'):raise RuntimeError('E-Mail-Benachrichtigungen sind deaktiviert')
    host=str(s.get('smtp_host','')).strip();port=int(s.get('smtp_port',587));security=str(s.get('smtp_security','starttls')).lower();username=str(s.get('smtp_username','')).strip();password=smtp_password(s);sender=str(s.get('mail_from','')).strip() or username;recipients=[x.strip() for x in str(s.get('mail_to','')).replace(';',',').split(',') if x.strip()]
    if not host or not sender or not recipients:raise RuntimeError('SMTP-Server, Absender und Empfänger müssen gesetzt sein')
    msg=EmailMessage();msg['Subject']=subject;msg['From']=sender;msg['To']=', '.join(recipients);msg.set_content(body);context=ssl.create_default_context()
    if security in {'ssl','smtps'}:
        with smtplib.SMTP_SSL(host,port,timeout=15,context=context) as smtp:
            if username:smtp.login(username,password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host,port,timeout=15) as smtp:
            smtp.ehlo()
            if security=='starttls':smtp.starttls(context=context);smtp.ehlo()
            if username:smtp.login(username,password)
            smtp.send_message(msg)
def send_telegram(message):
    s = load_settings()

    token = telegram_bot_token(s)
    chat_id = str(s.get('telegram_chat_id', '')).strip()

    if not token:
        raise RuntimeError('Telegram Bot-Token ist nicht gesetzt')

    if not chat_id:
        raise RuntimeError('Telegram Chat-ID ist nicht gesetzt')

    url = f'https://api.telegram.org/bot{token}/sendMessage'

    data = urllib.parse.urlencode({
        'chat_id': chat_id,
        'text': str(message),
        'disable_web_page_preview': 'true',
    }).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=data,
        method='POST',
        headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Keepalived-Monitor',
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            payload = json.loads(response.read().decode('utf-8'))

    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode('utf-8'))
            description = str(
                payload.get('description') or 'Telegram API-Fehler'
            )
        except Exception:
            description = f'Telegram API-Fehler (HTTP {e.code})'

        raise RuntimeError(description)

    except urllib.error.URLError as e:
        reason = str(getattr(e, 'reason', '') or '').strip()

        if reason:
            raise RuntimeError(
                f'Telegram API nicht erreichbar: {reason}'
            )

        raise RuntimeError('Telegram API nicht erreichbar')

    except TimeoutError:
        raise RuntimeError('Zeitüberschreitung beim Telegram-Versand')

    except json.JSONDecodeError:
        raise RuntimeError('Ungültige Antwort der Telegram API')

    if not payload.get('ok'):
        raise RuntimeError(
            str(payload.get('description') or 'Telegram-Versand fehlgeschlagen')
        )

    return True
def ssh(node,command,timeout=8):
    s=cfg().get('ssh',{});args=['ssh','-o','BatchMode=yes','-o',f"ConnectTimeout={s.get('connect_timeout',3)}"]
    if s.get('key_file'):args+=['-i',s['key_file']]
    if s.get('known_hosts_file'):args+=['-o',f"UserKnownHostsFile={s['known_hosts_file']}",'-o','StrictHostKeyChecking=yes']
    args += [f"{node.get('user','root')}@{node['host']}",command]
    try:r=subprocess.run(args,capture_output=True,text=True,timeout=timeout);return r.returncode,r.stdout.strip(),r.stderr.strip()
    except Exception as e:return 255,'',str(e)
def node_by_name(name):return next((n for n in cfg().get('nodes',[]) if n.get('name')==name),None)
def login_required(fn):
    @wraps(fn)
    def wrapped(*a,**kw):
        if not session.get('authenticated'):
            if request.path.startswith('/api/'):return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
            return redirect(url_for('login',next=request.path))
        return fn(*a,**kw)
    return wrapped
def csrf_ok():return secrets.compare_digest(str(session.get('csrf','')),str(request.headers.get('X-CSRF-Token','')))
def fmt_duration(start,end):
    try:
        sec=max(0,int((datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds()));d,sec=divmod(sec,86400);h,sec=divmod(sec,3600);m,s=divmod(sec,60);p=[]
        if d:p.append(f'{d} Tag(e)')
        if h:p.append(f'{h} Std.')
        if m:p.append(f'{m} Min.')
        if not p:p.append(f'{s} Sek.')
        return ' '.join(p)
    except Exception:return 'unbekannt'
def notification_cfg():
    s = load_settings()
    return {
        'notifications_enabled': bool(
            s.get('notifications_enabled', True)
        ),
        'node_down': bool(
            s.get('node_down', True)
        ),
        'failures_before_alert': max(
            1,
            min(20, int(s.get('failures_before_alert', 3)))
        ),
        'recovery_mail': bool(
            s.get('recovery_mail', True)
        ),
        'vrrp_failover': bool(
            s.get('vrrp_failover', True)
        ),
        'vrrp_health': bool(
            s.get('vrrp_health', True)
        ),
    }
def notification_status(name):
    st = notification_cfg()
    maintenance = maintenance_info(name)
    s = load_settings()

    channel_enabled = bool(
        s.get('mail_enabled') or s.get('telegram_enabled')
    )

    with sqlite3.connect(DB) as c:
        r = c.execute(
            '''
            SELECT failures,is_down,down_since,last_alert,last_recovery
            FROM node_alert_state
            WHERE name=?
            ''',
            (name,)
        ).fetchone()

    return {
        'enabled': (
            channel_enabled
            and st['notifications_enabled']
            and (
                st['node_down']
                or st['recovery_mail']
            )
            and not maintenance['active']
        ),
        'suppressed': maintenance['active'],
        'failures': r[0] if r else 0,
        'is_down': bool(r[1]) if r else False,
        'down_since': r[2] if r else None,
        'last_alert': r[3] if r else None,
        'last_recovery': r[4] if r else None,
        'failures_before_alert': st['failures_before_alert'],
    }
def send_node_notification(kind, name, node, now, down_since=None, failures=None):
    s = load_settings()

    if kind == 'RECOVERY':
        subject = f'🟢 Keepalived Monitor – {name} wieder ONLINE'
        body = (
            f'Node: {name}\n'
            f'Host: {node["host"]}\n'
            'Status: ONLINE\n'
            f'Zeitpunkt: {now}\n'
            f'Ausfallzeit: {fmt_duration(down_since, now)}'
        )
    elif kind == 'NODE DOWN':
        subject = f'🔴 Keepalived Monitor – Node DOWN: {name}'
        body = (
            f'Node: {name}\n'
            f'Host: {node["host"]}\n'
            'Status: NICHT ERREICHBAR\n'
            f'Zeitpunkt: {now}\n'
            f'Fehlgeschlagene Prüfungen: {failures}'
        )
    else:
        raise ValueError(f'Unbekannter Benachrichtigungstyp: {kind}')

    # E-Mail ist ein unabhängiger Kanal.
    if s.get('mail_enabled'):
        try:
            send_mail(subject, body)
            record_notification(kind, name, True, ts=now)
        except Exception as e:
            record_notification(kind, name, False, e, now)
            print(f'mail notification error {name}: {e}', flush=True)

    # Telegram ist ebenfalls unabhängig.
    if s.get('telegram_enabled'):
        try:
            send_telegram(f'{subject}\n\n{body}')
        except Exception as e:
            print(f'telegram notification error {name}: {e}', flush=True)
def send_vrrp_notification(name, old_master, new_master, now):
    s = load_settings()

    if not s.get('notifications_enabled', True):
        return

    event_type = classify_vrrp_event(old_master, new_master)

    if is_vrrp_health_event(old_master, new_master):

        if not s.get('vrrp_health', True):
            return
    else:
        if not s.get('vrrp_failover', True):
            return

    if event_type == 'SPLIT_BRAIN':
        subject = f'🔴 Keepalived Monitor – Mehrere VRRP MASTER: {name}'
        body = (
            f'VRRP-Instanz: {name}\n'
            f'Vorheriger Zustand: {old_master}\n'
            'Neuer Zustand: MEHRERE MASTER\n'
            f'Zeitpunkt: {now}'
        )
        kind = 'VRRP MULTIPLE'

    elif event_type == 'NO_MASTER':
        subject = f'🔴 Keepalived Monitor – Kein VRRP MASTER: {name}'
        body = (
            f'VRRP-Instanz: {name}\n'
            f'Alter MASTER: {old_master}\n'
            'Neuer MASTER: KEIN MASTER\n'
            f'Zeitpunkt: {now}'
        )
        kind = 'VRRP NO MASTER'

    elif event_type == 'NORMALIZED':
        subject = f'🟢 Keepalived Monitor – VRRP MASTER-Zustand normalisiert: {name}'
        body = (
            f'VRRP-Instanz: {name}\n'
            'Vorheriger Zustand: MEHRERE MASTER\n'
            f'Aktueller MASTER: {new_master}\n'
            f'Zeitpunkt: {now}'
        )
        kind = 'VRRP NORMALIZED'

    elif event_type == 'RECOVERY':
        subject = f'🟢 Keepalived Monitor – VRRP MASTER wieder verfügbar: {name}'
        body = (
            f'VRRP-Instanz: {name}\n'
            f'Alter MASTER: {old_master}\n'
            f'Neuer MASTER: {new_master}\n'
            f'Zeitpunkt: {now}'
        )
        kind = 'VRRP RECOVERY'

    else:
        subject = f'🔄 Keepalived Monitor – VRRP MASTER-Wechsel: {name}'
        body = (
            f'VRRP-Instanz: {name}\n'
            f'Alter MASTER: {old_master}\n'
            f'Neuer MASTER: {new_master}\n'
            f'Zeitpunkt: {now}'
        )
        kind = 'VRRP FAILOVER'

    if s.get('mail_enabled'):
        try:
            send_mail(subject, body)
            record_notification(kind, name, True, ts=now)
        except Exception as e:
            record_notification(kind, name, False, e, now)
            print(
                f'mail VRRP notification error {name}: {e}',
                flush=True
            )

    if s.get('telegram_enabled'):
        try:
            send_telegram(f'{subject}\n\n{body}')
        except Exception as e:
            print(
                f'telegram VRRP notification error {name}: {e}',
                flush=True
            )
def process_node_notifications(nodes):
    st = notification_cfg()

    if not st['notifications_enabled']:
        return

    if not st['node_down'] and not st['recovery_mail']:
        return

    now = datetime.now().isoformat(timespec='seconds')

    with notification_lock:
        for name, node in nodes.items():
            notification = None

            if maintenance_info(name)['active']:
                with sqlite3.connect(DB) as c:
                    c.execute(
                        '''
                        INSERT INTO node_alert_state(name,failures,is_down)
                        VALUES(?,0,0)
                        ON CONFLICT(name) DO UPDATE SET
                            failures=0,
                            is_down=0,
                            down_since=NULL
                        ''',
                        (name,)
                    )
                continue

            with sqlite3.connect(DB) as c:
                r = c.execute(
                    '''
                    SELECT failures,is_down,down_since,last_alert,last_recovery
                    FROM node_alert_state
                    WHERE name=?
                    ''',
                    (name,)
                ).fetchone()

                if r is None:
                    c.execute(
                        '''
                        INSERT INTO node_alert_state(name,failures,is_down)
                        VALUES(?,?,?)
                        ''',
                        (name, 0 if node['online'] else 1, 0)
                    )
                    continue

                failures, is_down, down_since, _, _ = r

                if node['online']:
                    if is_down:
                        c.execute(
                            '''
                            UPDATE node_alert_state
                            SET failures=0,
                                is_down=0,
                                down_since=NULL,
                                last_recovery=?
                            WHERE name=?
                            ''',
                            (now, name)
                        )

                        if st['recovery_mail']:
                            notification = {
                                'kind': 'RECOVERY',
                                'down_since': down_since,
                            }

                    elif failures:
                        c.execute(
                            '''
                            UPDATE node_alert_state
                            SET failures=0
                            WHERE name=?
                            ''',
                            (name,)
                        )

                else:
                    failures += 1

                    if (
                        not is_down
                        and failures >= st['failures_before_alert']
                    ):
                        c.execute(
                            '''
                            UPDATE node_alert_state
                            SET failures=?,
                                is_down=1,
                                down_since=?,
                                last_alert=?
                            WHERE name=?
                            ''',
                            (failures, now, now, name)
                        )

                        if st['node_down']:
                            notification = {
                                'kind': 'NODE DOWN',
                                'failures': failures,
                            }

                    else:
                        c.execute(
                            '''
                            UPDATE node_alert_state
                            SET failures=?
                            WHERE name=?
                            ''',
                            (failures, name)
                        )

            # Wichtig:
            # Erst hier ist die vorherige SQLite-Transaktion beendet.
            if notification:
                send_node_notification(
                    notification['kind'],
                    name,
                    node,
                    now,
                    down_since=notification.get('down_since'),
                    failures=notification.get('failures'),
                )
def poll_node(node):
    cmd="printf 'KEEP='; systemctl is-active keepalived 2>/dev/null || true; printf 'UP='; uptime -p 2>/dev/null || true; printf 'ADDR='; ip -j addr show 2>/dev/null || true";rc,out,err=ssh(node,cmd);d={'name':node['name'],'host':node['host'],'online':rc==0,'keepalived':'unknown','uptime':'-','addresses':[],'error':err if rc else ''}
    if rc:return d
    for line in out.splitlines():
        if line.startswith('KEEP='):d['keepalived']=line[5:].strip()
        elif line.startswith('UP='):d['uptime']=line[3:].strip()
        elif line.startswith('ADDR='):
            try:
                for itf in json.loads(line[5:]):
                    for a in itf.get('addr_info',[]):d['addresses'].append(a.get('local'))
            except Exception:pass
    return d
def record(name, new):
    event = None

    with sqlite3.connect(DB) as c:
        r = c.execute(
            'SELECT master FROM state WHERE name=?',
            (name,)
        ).fetchone()

        old = r[0] if r else None

        if old != new:
            if r:
                c.execute(
                    'UPDATE state SET master=? WHERE name=?',
                    (new, name)
                )
            else:
                c.execute(
                    'INSERT INTO state(name,master) VALUES(?,?)',
                    (name, new)
                )

            if old is not None:
                now = datetime.now().isoformat(timespec='seconds')

                c.execute(
                    '''
                    INSERT INTO events(ts,name,old_master,new_master)
                    VALUES(?,?,?,?)
                    ''',
                    (now, name, old, new)
                )

                event = {
                    'name': name,
                    'old_master': old,
                    'new_master': new,
                    'ts': now,
                }

    return event
def vrrp_metrics(name):
    with sqlite3.connect(DB) as c:
        rows = c.execute(
            '''
            SELECT ts, old_master, new_master
            FROM events
            WHERE name=?
            ORDER BY id DESC
            ''',
            (name,)
        ).fetchall()

    metrics = {
        'failovers': 0,
        'no_master': 0,
        'split_brain': 0,
        'recoveries': 0,
        'normalized': 0,
        'last_change': rows[0][0] if rows else None,
        'last_failover': None,
        'last_critical': None,
    }

    for ts, old_master, new_master in rows:
        event_type = classify_vrrp_event(old_master, new_master)

        if event_type == 'FAILOVER':
            metrics['failovers'] += 1
            if metrics['last_failover'] is None:
                metrics['last_failover'] = ts

        elif event_type == 'NO_MASTER':
            metrics['no_master'] += 1
            if metrics['last_critical'] is None:
                metrics['last_critical'] = ts

        elif event_type == 'SPLIT_BRAIN':
            metrics['split_brain'] += 1
            if metrics['last_critical'] is None:
                metrics['last_critical'] = ts

        elif event_type == 'RECOVERY':
            metrics['recoveries'] += 1

        elif event_type == 'NORMALIZED':
            metrics['normalized'] += 1

    return metrics
def cluster_health(nodes,vrrp):
    diagnosis=validate_cluster(nodes,vrrp)

    status_map={
        'OK':'HEALTHY',
        'WARNING':'DEGRADED',
        'ERROR':'CRITICAL',
        'UNKNOWN':'UNKNOWN',
    }

    issues=[
        check['message']
        for instance in diagnosis.get('instances',[])
        for check in instance.get('checks',[])
        if check.get('level') in {'WARNING','ERROR','UNKNOWN'}
    ]

    return {
        'status':status_map.get(diagnosis.get('status'),'UNKNOWN'),
        'message':diagnosis.get('message','Clusterzustand kann nicht bestimmt werden'),
        'issues':issues,
        'diagnosis':diagnosis,
    }
def poll():
    c=cfg();ns={n['name']:poll_node(n) for n in c.get('nodes',[])}
    for name in ns:ns[name]['maintenance']=maintenance_info(name)
    record_availability(ns);process_node_notifications(ns)
    for name in ns:ns[name]['notification']=notification_status(name)
    vs=[]

    for v in c.get('vrrp', []):
        owners = [
            name
            for name in v.get('nodes', [])
            if v['vip'] in ns.get(name, {}).get('addresses', [])
        ]

        master = (
            owners[0]
            if len(owners) == 1
            else ('MULTIPLE' if len(owners) > 1 else None)
        )

        event = record(
            v['name'],
            master or 'NONE'
        )

        if event:
            send_vrrp_notification(
                event['name'],
                event['old_master'],
                event['new_master'],
                event['ts'],
            )

        roles = {
            name: ('MASTER' if name == master else 'BACKUP')
            for name in v.get('nodes', [])
        }

        vs.append({
            **v,
            'master': master,
            'healthy': len(owners) == 1,
            'roles': roles,
            **vrrp_metrics(v['name']),
        })

    with lock:
        cache.update(
            nodes=ns,
            vrrp=vs,
            cluster=cluster_health(ns,vs),
            updated=datetime.now().isoformat(timespec='seconds')
        )
def loop():
    while True:
        try:poll()
        except Exception as e:print('poll error',e,flush=True)
        time.sleep(max(2,int(cfg().get('refresh_seconds',5))))
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=os.getenv('ADMIN_USERNAME','');p=os.getenv('ADMIN_PASSWORD','')
        if u and p and secrets.compare_digest(request.form.get('username',''),u) and secrets.compare_digest(request.form.get('password',''),p):session.clear();session['authenticated']=True;session['csrf']=secrets.token_urlsafe(32);return redirect(request.args.get('next') or url_for('index'))
        return render_template('login.html',error='Benutzername oder Passwort ist falsch.'),401
    return render_template('login.html',error=None)
@app.post('/logout')
@login_required
def logout():session.clear();return redirect(url_for('login'))
@app.route('/')
@login_required
def index():return render_template('index.html',nodes=cfg().get('nodes',[]),csrf=session['csrf'])
@app.route('/node/<name>')
@login_required
def node_page(name):
    node=node_by_name(name)
    if not node:return 'Node nicht gefunden',404
    return render_template('node.html',nodes=cfg().get('nodes',[]),node=node,csrf=session['csrf'])
@app.route('/settings')
@login_required
def settings_page():return render_template('settings.html',nodes=cfg().get('nodes',[]),csrf=session['csrf'])
@app.get('/api/settings')
@login_required
def get_settings():return jsonify(public_settings())
@app.post('/api/settings')
@login_required
def update_settings():
    if not csrf_ok():
        return jsonify({'ok': False, 'error': 'Ungültiges CSRF-Token'}), 403

    try:
        d = request.get_json(force=True) or {}
        s = load_settings()

        security = str(d.get('smtp_security', 'starttls')).lower()
        port = int(d.get('smtp_port', 587))
        failures = int(d.get('failures_before_alert', 3))

        if security not in {'starttls', 'ssl', 'smtps', 'none'}:
            raise ValueError('Ungültige SMTP-Verschlüsselung')

        if not 1 <= port <= 65535:
            raise ValueError('SMTP-Port muss zwischen 1 und 65535 liegen')

        if not 1 <= failures <= 20:
            raise ValueError('Fehlversuche müssen zwischen 1 und 20 liegen')

        # Telegram
        telegram_enabled = bool(d.get('telegram_enabled'))
        telegram_chat_id = str(d.get('telegram_chat_id', '')).strip()
        telegram_token = str(d.get('telegram_bot_token', '')).strip()

        # Ein leeres Token-Feld bedeutet:
        # Bereits gespeicherten Token unverändert beibehalten.
        telegram_token_available = bool(
            telegram_token or s.get('telegram_bot_token_enc')
        )

        if telegram_enabled:
            if not telegram_token_available:
                raise ValueError(
                    'Für Telegram muss ein Bot-Token hinterlegt sein'
                )

            if not telegram_chat_id:
                raise ValueError(
                    'Für Telegram muss eine Chat-ID hinterlegt sein'
                )

        s.update(
            mail_enabled=bool(d.get('mail_enabled')),
            notifications_enabled=bool(
                d.get('notifications_enabled', True)
            ),
            node_down=bool(d.get('node_down')),
            recovery_mail=bool(d.get('recovery_mail')),
            vrrp_failover=bool(
                d.get('vrrp_failover', s.get('vrrp_failover', True))
            ),
            vrrp_health=bool(
                d.get('vrrp_health', s.get('vrrp_health', True))
            ),
            failures_before_alert=failures,
            smtp_host=str(d.get('smtp_host', '')).strip(),
            smtp_port=port,
            smtp_security=security,
            smtp_username=str(d.get('smtp_username', '')).strip(),
            mail_from=str(d.get('mail_from', '')).strip(),
            mail_to=str(d.get('mail_to', '')).strip(),

            telegram_enabled=telegram_enabled,
            telegram_chat_id=telegram_chat_id,
        )

        # SMTP-Passwort nur ersetzen, wenn tatsächlich eines
        # übermittelt wurde.
        if str(d.get('smtp_password', '')):
            s['smtp_password_enc'] = fernet().encrypt(
                str(d['smtp_password']).encode()
            ).decode()

        # Telegram-Token ebenfalls nur ersetzen, wenn ein neuer
        # Token übermittelt wurde.
        if telegram_token:
            s['telegram_bot_token_enc'] = fernet().encrypt(
                telegram_token.encode()
            ).decode()

        save_settings(s)

        return jsonify({
            'ok': True,
            'settings': public_settings(),
        })

    except Exception as e:
        return jsonify({
            'ok': False,
            'error': str(e),
        }), 400
@app.post('/api/notifications/test')
@login_required
def test_notification():
    if not csrf_ok():return jsonify({'ok':False,'error':'Ungültiges CSRF-Token'}),403
    now=datetime.now().isoformat(timespec='seconds')
    try:send_mail('Keepalived Monitor – Testmail',f'Dies ist eine Testmail des Keepalived Monitors.\n\nZeitpunkt: {now}\nSMTP-Konfiguration: erfolgreich.');record_notification('TEST',None,True,ts=now);s=load_settings();s['last_test']=now;s['last_test_ok']=True;save_settings(s);return jsonify({'ok':True})
    except Exception as e:record_notification('TEST',None,False,e,now);s=load_settings();s['last_test']=now;s['last_test_ok']=False;save_settings(s);return jsonify({'ok':False,'error':str(e)}),502
@app.post('/api/notifications/telegram/test')
@login_required
def test_telegram_notification():
    if not csrf_ok():
        return jsonify({
            'ok': False,
            'error': 'Ungültiges CSRF-Token',
        }), 403

    now = datetime.now().isoformat(timespec='seconds')

    try:
        send_telegram(
            'Keepalived Monitor – Telegram-Test\n\n'
            'Dies ist eine Testnachricht des Keepalived Monitors.\n\n'
            f'Zeitpunkt: {now}\n'
            'Telegram-Konfiguration: erfolgreich.'
        )

        s = load_settings()
        s['telegram_last_test'] = now
        s['telegram_last_test_ok'] = True
        save_settings(s)

        return jsonify({
            'ok': True,
        })

    except Exception as e:
        s = load_settings()
        s['telegram_last_test'] = now
        s['telegram_last_test_ok'] = False
        save_settings(s)

        return jsonify({
            'ok': False,
            'error': str(e),
        }), 502
@app.get('/api/notifications/history')
@login_required
def notification_history():
    try:limit=max(1,min(100,int(request.args.get('limit',50))))
    except ValueError:limit=50
    with sqlite3.connect(DB) as c:r=c.execute('SELECT ts,type,node,ok,error FROM notification_history ORDER BY id DESC LIMIT ?',(limit,)).fetchall()
    return jsonify([{'ts':x[0],'type':x[1],'node':x[2],'ok':bool(x[3]),'error':x[4]} for x in r])
@app.route('/api/status')
@login_required
def status():
    with lock:return jsonify(cache)
@app.get('/api/availability')
@login_required
def availability():return jsonify(availability_stats())
@app.route('/api/history')
@login_required
def history():
    with sqlite3.connect(DB) as c:
        rows = c.execute(
            '''
            SELECT ts,name,old_master,new_master
            FROM events
            ORDER BY id DESC
            LIMIT 50
            '''
        ).fetchall()

    return jsonify([
        {
            'ts': row[0],
            'name': row[1],
            'old': row[2],
            'new': row[3],
            'type': classify_vrrp_event(row[2], row[3]),
        }
        for row in rows
    ])@app.post('/api/nodes/<name>/maintenance')
@login_required
def node_maintenance(name):
    if not csrf_ok():return jsonify({'ok':False,'error':'Ungültiges CSRF-Token'}),403
    if not node_by_name(name):return jsonify({'ok':False,'error':'Node nicht gefunden'}),404
    d=request.get_json(silent=True) or {};active=bool(d.get('active'));set_maintenance(name,active)
    try:poll()
    except Exception:pass
    return jsonify({'ok':True,'maintenance':maintenance_info(name)})
@app.post('/api/nodes/<name>/keepalived/<action>')
@login_required
def keepalived_action(name,action):
    if not csrf_ok():return jsonify({'ok':False,'error':'Ungültiges CSRF-Token'}),403
    if action not in {'start','stop','restart'}:return jsonify({'ok':False,'error':'Aktion nicht erlaubt'}),400
    node=node_by_name(name)
    if not node:return jsonify({'ok':False,'error':'Node nicht gefunden'}),404
    rc,out,err=ssh(node,f'systemctl {action} keepalived',12)
    if rc!=0:return jsonify({'ok':False,'status':'unknown','error':err or out or f'systemctl {action} fehlgeschlagen'}),502
    _,so,se=ssh(node,'systemctl is-active keepalived',8);st=so.splitlines()[-1].strip() if so else 'unknown';expected={'start':'active','restart':'active','stop':'inactive'}[action];ok=st==expected
    try:poll()
    except Exception:pass
    return jsonify({'ok':ok,'status':st,'error':'' if ok else (se or f'Erwarteter Status {expected}, erhalten: {st}')}),200 if ok else 502
@app.get('/api/nodes/<name>/keepalived/logs')
@login_required
def keepalived_logs(name):
    node=node_by_name(name)
    if not node:return jsonify({'ok':False,'error':'Node nicht gefunden'}),404
    try:lines=max(20,min(500,int(request.args.get('lines',100))))
    except ValueError:lines=100
    rc,out,err=ssh(node,f'journalctl -u keepalived -n {lines} --no-pager --output=short-iso',12);return jsonify({'ok':rc==0,'node':name,'lines':lines,'logs':out,'error':err}),200 if rc==0 else 502
@app.route('/healthz')
def healthz():return {'ok':True}
db_init();poll();threading.Thread(target=loop,daemon=True).start()