import base64, hashlib, json, os, secrets, sqlite3, subprocess, threading, time, smtplib, ssl
from datetime import datetime
from email.message import EmailMessage
from functools import wraps
from flask import Flask, jsonify, render_template, request, redirect, session, url_for
from cryptography.fernet import Fernet, InvalidToken
import yaml

app=Flask(__name__)
app.secret_key=os.getenv('SECRET_KEY') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','false').lower()=='true')
CONFIG_FILE=os.getenv('CONFIG_FILE','/app/config/config.yml'); DB='/app/data/history.db'; SETTINGS_FILE='/app/data/settings.json'
lock=threading.Lock(); notification_lock=threading.Lock(); settings_lock=threading.Lock(); cache={'nodes':{},'vrrp':[],'cluster':{'status':'UNKNOWN','message':'Noch keine Daten'},'updated':None}
def cfg():
    with open(CONFIG_FILE,encoding='utf-8') as f:return yaml.safe_load(f) or {}
def db_init():
    os.makedirs(os.path.dirname(DB),exist_ok=True)
    with sqlite3.connect(DB) as c:c.execute('CREATE TABLE IF NOT EXISTS state (name TEXT PRIMARY KEY, master TEXT)');c.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, name TEXT, old_master TEXT, new_master TEXT)');c.execute('CREATE TABLE IF NOT EXISTS node_alert_state (name TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0, is_down INTEGER NOT NULL DEFAULT 0, down_since TEXT, last_alert TEXT, last_recovery TEXT)')
def fernet():return Fernet(base64.urlsafe_b64encode(hashlib.sha256(str(app.secret_key).encode()).digest()))
def env_bool(n,d=False):return os.getenv(n,str(d)).lower() in {'1','true','yes','on'}
def defaults():
    n=(cfg().get('notifications',{}).get('node_down',{}) or {});return {'mail_enabled':env_bool('MAIL_ENABLED'),'node_down':bool(n.get('enabled',True)),'recovery_mail':bool(n.get('recovery_mail',True)),'failures_before_alert':max(1,int(n.get('failures_before_alert',3))),'smtp_host':os.getenv('SMTP_HOST',''),'smtp_port':int(os.getenv('SMTP_PORT','587')),'smtp_security':os.getenv('SMTP_SECURITY','starttls').lower(),'smtp_username':os.getenv('SMTP_USERNAME',''),'smtp_password_enc':'','mail_from':os.getenv('MAIL_FROM',''),'mail_to':os.getenv('MAIL_TO',''),'last_test':None,'last_test_ok':None,'maintenance_nodes':{}}
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
    m=load_settings().get('maintenance_nodes',{}).get(name)
    return {'active':bool(m),'since':m.get('since') if isinstance(m,dict) else None}
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
def public_settings():
    s=load_settings();return {k:v for k,v in s.items() if k not in {'smtp_password_enc','maintenance_nodes'}}|{'smtp_password_set':bool(s.get('smtp_password_enc') or os.getenv('SMTP_PASSWORD',''))}
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
    s=load_settings();return {'enabled':bool(s.get('node_down',True)),'failures_before_alert':max(1,min(20,int(s.get('failures_before_alert',3)))),'recovery_mail':bool(s.get('recovery_mail',True))}
def notification_status(name):
    st=notification_cfg();maintenance=maintenance_info(name)
    with sqlite3.connect(DB) as c:r=c.execute('SELECT failures,is_down,down_since,last_alert,last_recovery FROM node_alert_state WHERE name=?',(name,)).fetchone()
    return {'enabled':mail_enabled() and st['enabled'] and not maintenance['active'],'suppressed':maintenance['active'],'failures':r[0] if r else 0,'is_down':bool(r[1]) if r else False,'down_since':r[2] if r else None,'last_alert':r[3] if r else None,'last_recovery':r[4] if r else None,'failures_before_alert':st['failures_before_alert']}
def process_node_notifications(nodes):
    st=notification_cfg()
    if not st['enabled']:return
    now=datetime.now().isoformat(timespec='seconds')
    with notification_lock:
        for name,node in nodes.items():
            if maintenance_info(name)['active']:
                with sqlite3.connect(DB) as c:c.execute('INSERT INTO node_alert_state(name,failures,is_down) VALUES(?,0,0) ON CONFLICT(name) DO UPDATE SET failures=0,is_down=0,down_since=NULL',(name,))
                continue
            with sqlite3.connect(DB) as c:
                r=c.execute('SELECT failures,is_down,down_since,last_alert,last_recovery FROM node_alert_state WHERE name=?',(name,)).fetchone()
                if r is None:c.execute('INSERT INTO node_alert_state(name,failures,is_down) VALUES(?,?,?)',(name,0 if node['online'] else 1,0));continue
                failures,is_down,down_since,_,_=r
                if node['online']:
                    if is_down:
                        if mail_enabled() and st['recovery_mail']:
                            try:send_mail(f'🟢 Keepalived Monitor – {name} wieder ONLINE',f'Node: {name}\nHost: {node["host"]}\nStatus: ONLINE\nZeitpunkt: {now}\nAusfallzeit: {fmt_duration(down_since,now)}')
                            except Exception as e:print(f'mail recovery error {name}: {e}',flush=True);continue
                        c.execute('UPDATE node_alert_state SET failures=0,is_down=0,down_since=NULL,last_recovery=? WHERE name=?',(now,name))
                    elif failures:c.execute('UPDATE node_alert_state SET failures=0 WHERE name=?',(name,))
                else:
                    failures+=1
                    if not is_down and failures>=st['failures_before_alert']:
                        if mail_enabled():
                            try:send_mail(f'🔴 Keepalived Monitor – Node DOWN: {name}',f'Node: {name}\nHost: {node["host"]}\nStatus: NICHT ERREICHBAR\nZeitpunkt: {now}\nFehlgeschlagene Prüfungen: {failures}')
                            except Exception as e:print(f'mail alert error {name}: {e}',flush=True);c.execute('UPDATE node_alert_state SET failures=? WHERE name=?',(failures,name));continue
                        c.execute('UPDATE node_alert_state SET failures=?,is_down=1,down_since=?,last_alert=? WHERE name=?',(failures,now,now,name))
                    else:c.execute('UPDATE node_alert_state SET failures=? WHERE name=?',(failures,name))
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
def record(name,new):
    with sqlite3.connect(DB) as c:
        r=c.execute('SELECT master FROM state WHERE name=?',(name,)).fetchone();old=r[0] if r else None
        if old!=new:
            if r:c.execute('UPDATE state SET master=? WHERE name=?',(new,name))
            else:c.execute('INSERT INTO state(name,master) VALUES(?,?)',(name,new))
            if old is not None:c.execute('INSERT INTO events(ts,name,old_master,new_master) VALUES(?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),name,old,new))
def vrrp_metrics(name):
    with sqlite3.connect(DB) as c:r=c.execute('SELECT ts FROM events WHERE name=? ORDER BY id DESC',(name,)).fetchall()
    return {'failovers':len(r),'last_change':r[0][0] if r else None}
def cluster_health(nodes,vrrp):
    critical=[];degraded=[]
    for v in vrrp:
        if not v['healthy']:critical.append(f"{v['name']}: {'mehrere MASTER erkannt' if v['master']=='MULTIPLE' else 'kein MASTER'}")
    if critical:return {'status':'CRITICAL','message':' · '.join(critical),'issues':critical}
    for n in nodes.values():
        if n.get('maintenance',{}).get('active'):continue
        if not n['online']:degraded.append(f"{n['name']} ist offline")
        elif n['keepalived']!='active':degraded.append(f"Keepalived auf {n['name']} ist {n['keepalived']}")
    if degraded:return {'status':'DEGRADED','message':'Redundanz eingeschränkt: '+' · '.join(degraded),'issues':degraded}
    if nodes and vrrp:return {'status':'HEALTHY','message':'Cluster vollständig funktions- und failoverbereit','issues':[]}
    return {'status':'UNKNOWN','message':'Clusterzustand kann nicht bestimmt werden','issues':[]}
def poll():
    c=cfg();ns={n['name']:poll_node(n) for n in c.get('nodes',[])}
    for name in ns:ns[name]['maintenance']=maintenance_info(name)
    process_node_notifications(ns)
    for name in ns:ns[name]['notification']=notification_status(name)
    vs=[]
    for v in c.get('vrrp',[]):
        owners=[name for name in v.get('nodes',[]) if v['vip'] in ns.get(name,{}).get('addresses',[])];master=owners[0] if len(owners)==1 else ('MULTIPLE' if len(owners)>1 else None);record(v['name'],master or 'NONE');roles={name:('MASTER' if name==master else 'BACKUP') for name in v.get('nodes',[])};vs.append({**v,'master':master,'healthy':len(owners)==1,'roles':roles,**vrrp_metrics(v['name'])})
    with lock:cache.update(nodes=ns,vrrp=vs,cluster=cluster_health(ns,vs),updated=datetime.now().isoformat(timespec='seconds'))
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
    if not csrf_ok():return jsonify({'ok':False,'error':'Ungültiges CSRF-Token'}),403
    try:
        d=request.get_json(force=True) or {};s=load_settings();security=str(d.get('smtp_security','starttls')).lower();port=int(d.get('smtp_port',587));failures=int(d.get('failures_before_alert',3))
        if security not in {'starttls','ssl','smtps','none'}:raise ValueError('Ungültige SMTP-Verschlüsselung')
        if not 1<=port<=65535:raise ValueError('SMTP-Port muss zwischen 1 und 65535 liegen')
        if not 1<=failures<=20:raise ValueError('Fehlversuche müssen zwischen 1 und 20 liegen')
        s.update(mail_enabled=bool(d.get('mail_enabled')),node_down=bool(d.get('node_down')),recovery_mail=bool(d.get('recovery_mail')),failures_before_alert=failures,smtp_host=str(d.get('smtp_host','')).strip(),smtp_port=port,smtp_security=security,smtp_username=str(d.get('smtp_username','')).strip(),mail_from=str(d.get('mail_from','')).strip(),mail_to=str(d.get('mail_to','')).strip())
        if str(d.get('smtp_password','')):s['smtp_password_enc']=fernet().encrypt(str(d['smtp_password']).encode()).decode()
        save_settings(s);return jsonify({'ok':True,'settings':public_settings()})
    except Exception as e:return jsonify({'ok':False,'error':str(e)}),400
@app.post('/api/notifications/test')
@login_required
def test_notification():
    if not csrf_ok():return jsonify({'ok':False,'error':'Ungültiges CSRF-Token'}),403
    now=datetime.now().isoformat(timespec='seconds')
    try:send_mail('Keepalived Monitor – Testmail',f'Dies ist eine Testmail des Keepalived Monitors.\n\nZeitpunkt: {now}\nSMTP-Konfiguration: erfolgreich.');s=load_settings();s['last_test']=now;s['last_test_ok']=True;save_settings(s);return jsonify({'ok':True})
    except Exception as e:s=load_settings();s['last_test']=now;s['last_test_ok']=False;save_settings(s);return jsonify({'ok':False,'error':str(e)}),502
@app.route('/api/status')
@login_required
def status():
    with lock:return jsonify(cache)
@app.route('/api/history')
@login_required
def history():
    with sqlite3.connect(DB) as c:r=c.execute('SELECT ts,name,old_master,new_master FROM events ORDER BY id DESC LIMIT 50').fetchall()
    return jsonify([{'ts':x[0],'name':x[1],'old':x[2],'new':x[3],'type':'LOST' if x[3]=='NONE' else ('RECOVERED' if x[2]=='NONE' else 'FAILOVER')} for x in r])
@app.post('/api/nodes/<name>/maintenance')
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
