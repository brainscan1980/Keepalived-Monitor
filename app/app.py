import json, os, secrets, sqlite3, subprocess, threading, time
from datetime import datetime
from functools import wraps
from flask import Flask, jsonify, render_template, request, redirect, session, url_for
import yaml

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','false').lower()=='true')
CONFIG_FILE=os.getenv('CONFIG_FILE','/app/config/config.yml'); DB='/app/data/history.db'; lock=threading.Lock()
cache={'nodes':{},'vrrp':[],'cluster':{'status':'UNKNOWN','message':'Noch keine Daten'},'updated':None}

def cfg():
    with open(CONFIG_FILE,encoding='utf-8') as f:return yaml.safe_load(f)
def db_init():
    os.makedirs(os.path.dirname(DB),exist_ok=True)
    with sqlite3.connect(DB) as c:
        c.execute('CREATE TABLE IF NOT EXISTS state (name TEXT PRIMARY KEY, master TEXT)'); c.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, name TEXT, old_master TEXT, new_master TEXT)')
def ssh(node,command,timeout=8):
    s=cfg().get('ssh',{}); args=['ssh','-o','BatchMode=yes','-o',f"ConnectTimeout={s.get('connect_timeout',3)}"]
    if s.get('key_file'):args+=['-i',s['key_file']]
    if s.get('known_hosts_file'):args+=['-o',f"UserKnownHostsFile={s['known_hosts_file']}",'-o','StrictHostKeyChecking=yes']
    args += [f"{node.get('user','root')}@{node['host']}",command]
    try:
        r=subprocess.run(args,capture_output=True,text=True,timeout=timeout); return r.returncode,r.stdout.strip(),r.stderr.strip()
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
def poll_node(node):
    cmd="printf 'KEEP='; systemctl is-active keepalived 2>/dev/null || true; printf 'UP='; uptime -p 2>/dev/null || true; printf 'ADDR='; ip -j addr show 2>/dev/null || true"
    rc,out,err=ssh(node,cmd); d={'name':node['name'],'host':node['host'],'online':rc==0,'keepalived':'unknown','uptime':'-','addresses':[],'error':err if rc else ''}
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
        row=c.execute('SELECT master FROM state WHERE name=?',(name,)).fetchone(); old=row[0] if row else None
        if old!=new:
            if row:c.execute('UPDATE state SET master=? WHERE name=?',(new,name))
            else:c.execute('INSERT INTO state(name,master) VALUES(?,?)',(name,new))
            if old is not None:c.execute('INSERT INTO events(ts,name,old_master,new_master) VALUES(?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),name,old,new))
def vrrp_metrics(name):
    with sqlite3.connect(DB) as c:rows=c.execute('SELECT ts FROM events WHERE name=? ORDER BY id DESC',(name,)).fetchall()
    return {'failovers':len(rows),'last_change':rows[0][0] if rows else None}
def cluster_health(nodes,vrrp):
    critical=[]; degraded=[]
    for v in vrrp:
        if not v['healthy']:critical.append(f"{v['name']}: {'mehrere MASTER erkannt' if v['master']=='MULTIPLE' else 'kein MASTER'}")
    if critical:return {'status':'CRITICAL','message':' · '.join(critical),'issues':critical}
    for n in nodes.values():
        if not n['online']:degraded.append(f"{n['name']} ist offline")
        elif n['keepalived']!='active':degraded.append(f"Keepalived auf {n['name']} ist {n['keepalived']}")
    if degraded:return {'status':'DEGRADED','message':'Redundanz eingeschränkt: '+' · '.join(degraded),'issues':degraded}
    if nodes and vrrp:return {'status':'HEALTHY','message':'Cluster vollständig funktions- und failoverbereit','issues':[]}
    return {'status':'UNKNOWN','message':'Clusterzustand kann nicht bestimmt werden','issues':[]}
def poll():
    c=cfg(); ns={n['name']:poll_node(n) for n in c.get('nodes',[])}; vs=[]
    for v in c.get('vrrp',[]):
        owners=[name for name in v.get('nodes',[]) if v['vip'] in ns.get(name,{}).get('addresses',[])]; master=owners[0] if len(owners)==1 else ('MULTIPLE' if len(owners)>1 else None); record(v['name'],master or 'NONE'); roles={name:('MASTER' if name==master else 'BACKUP') for name in v.get('nodes',[])}; vs.append({**v,'master':master,'healthy':len(owners)==1,'roles':roles,**vrrp_metrics(v['name'])})
    with lock:cache.update(nodes=ns,vrrp=vs,cluster=cluster_health(ns,vs),updated=datetime.now().isoformat(timespec='seconds'))
def loop():
    while True:
        try:poll()
        except Exception as e:print('poll error',e,flush=True)
        time.sleep(max(2,int(cfg().get('refresh_seconds',5))))

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        user=os.getenv('ADMIN_USERNAME',''); password=os.getenv('ADMIN_PASSWORD','')
        if user and password and secrets.compare_digest(request.form.get('username',''),user) and secrets.compare_digest(request.form.get('password',''),password):
            session.clear(); session['authenticated']=True; session['csrf']=secrets.token_urlsafe(32); return redirect(request.args.get('next') or url_for('index'))
        return render_template('login.html',error='Benutzername oder Passwort ist falsch.'),401
    return render_template('login.html',error=None)
@app.post('/logout')
@login_required
def logout():session.clear(); return redirect(url_for('login'))
@app.route('/')
@login_required
def index():return render_template('index.html',nodes=cfg().get('nodes',[]),csrf=session['csrf'])
@app.route('/node/<name>')
@login_required
def node_page(name):
    node=node_by_name(name)
    if not node:return 'Node nicht gefunden',404
    return render_template('node.html',nodes=cfg().get('nodes',[]),node=node,csrf=session['csrf'])
@app.route('/api/status')
@login_required
def status():
    with lock:return jsonify(cache)
@app.route('/api/history')
@login_required
def history():
    with sqlite3.connect(DB) as c:rows=c.execute('SELECT ts,name,old_master,new_master FROM events ORDER BY id DESC LIMIT 50').fetchall()
    return jsonify([{'ts':r[0],'name':r[1],'old':r[2],'new':r[3],'type':'LOST' if r[3]=='NONE' else ('RECOVERED' if r[2]=='NONE' else 'FAILOVER')} for r in rows])
@app.post('/api/nodes/<name>/keepalived/<action>')
@login_required
def keepalived_action(name,action):
    if not csrf_ok():return jsonify({'ok':False,'error':'Ungültiges CSRF-Token'}),403
    if action not in {'start','stop','restart'}:return jsonify({'ok':False,'error':'Aktion nicht erlaubt'}),400
    node=node_by_name(name)
    if not node:return jsonify({'ok':False,'error':'Node nicht gefunden'}),404
    rc,out,err=ssh(node,f'systemctl {action} keepalived && systemctl is-active keepalived',12)
    try:poll()
    except Exception:pass
    return jsonify({'ok':rc==0,'status':out.splitlines()[-1] if out else 'unknown','error':err}),200 if rc==0 else 502
@app.get('/api/nodes/<name>/keepalived/logs')
@login_required
def keepalived_logs(name):
    node=node_by_name(name)
    if not node:return jsonify({'ok':False,'error':'Node nicht gefunden'}),404
    try:lines=max(20,min(500,int(request.args.get('lines',100))))
    except ValueError:lines=100
    rc,out,err=ssh(node,f'journalctl -u keepalived -n {lines} --no-pager --output=short-iso',12)
    return jsonify({'ok':rc==0,'node':name,'lines':lines,'logs':out,'error':err}),200 if rc==0 else 502
@app.route('/healthz')
def healthz():return {'ok':True}

db_init(); poll(); threading.Thread(target=loop,daemon=True).start()
