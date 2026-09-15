import json, os, sqlite3, subprocess, threading, time
from datetime import datetime
from flask import Flask, jsonify, render_template
import yaml

app = Flask(__name__)
CONFIG_FILE = os.getenv('CONFIG_FILE','/app/config/config.yml')
DB='/app/data/history.db'
lock=threading.Lock()
cache={'nodes':{},'vrrp':[],'cluster':{'status':'UNKNOWN','message':'Noch keine Daten'},'updated':None}

def cfg():
    with open(CONFIG_FILE, encoding='utf-8') as f: return yaml.safe_load(f)

def db_init():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with sqlite3.connect(DB) as c:
        c.execute('CREATE TABLE IF NOT EXISTS state (name TEXT PRIMARY KEY, master TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, name TEXT, old_master TEXT, new_master TEXT)')

def ssh(node, command):
    c=cfg(); s=c.get('ssh',{})
    args=['ssh','-o','BatchMode=yes','-o',f"ConnectTimeout={s.get('connect_timeout',3)}"]
    if s.get('key_file'): args += ['-i',s['key_file']]
    if s.get('known_hosts_file'): args += ['-o',f"UserKnownHostsFile={s['known_hosts_file']}",'-o','StrictHostKeyChecking=yes']
    args += [f"{node.get('user','root')}@{node['host']}",command]
    try:
        r=subprocess.run(args,capture_output=True,text=True,timeout=6)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e: return 255,'',str(e)

def poll_node(node):
    cmd="printf 'KEEP='; systemctl is-active keepalived 2>/dev/null || true; printf 'UP='; uptime -p 2>/dev/null || true; printf 'ADDR='; ip -j addr show 2>/dev/null || true"
    rc,out,err=ssh(node,cmd)
    d={'name':node['name'],'host':node['host'],'online':rc==0,'keepalived':'unknown','uptime':'-','addresses':[],'error':err if rc else ''}
    if rc: return d
    for line in out.splitlines():
        if line.startswith('KEEP='): d['keepalived']=line[5:].strip()
        elif line.startswith('UP='): d['uptime']=line[3:].strip()
        elif line.startswith('ADDR='):
            try:
                for itf in json.loads(line[5:]):
                    for a in itf.get('addr_info',[]): d['addresses'].append(a.get('local'))
            except Exception: pass
    return d

def record(name,new):
    with sqlite3.connect(DB) as c:
        row=c.execute('SELECT master FROM state WHERE name=?',(name,)).fetchone(); old=row[0] if row else None
        if old != new:
            if row: c.execute('UPDATE state SET master=? WHERE name=?',(new,name))
            else: c.execute('INSERT INTO state(name,master) VALUES(?,?)',(name,new))
            if old is not None: c.execute('INSERT INTO events(ts,name,old_master,new_master) VALUES(?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),name,old,new))

def vrrp_metrics(name):
    with sqlite3.connect(DB) as c:
        rows=c.execute('SELECT ts,old_master,new_master FROM events WHERE name=? ORDER BY id DESC',(name,)).fetchall()
    return {
        'failovers': len(rows),
        'last_change': rows[0][0] if rows else None
    }

def cluster_health(nodes, vrrp):
    critical=[]; degraded=[]
    for v in vrrp:
        if not v['healthy']:
            if v['master']=='MULTIPLE': critical.append(f"{v['name']}: mehrere MASTER erkannt")
            else: critical.append(f"{v['name']}: kein MASTER")
    if critical:
        return {'status':'CRITICAL','message':' · '.join(critical),'issues':critical}
    for n in nodes.values():
        if not n['online']: degraded.append(f"{n['name']} ist offline")
        elif n['keepalived']!='active': degraded.append(f"Keepalived auf {n['name']} ist {n['keepalived']}")
    if degraded:
        return {'status':'DEGRADED','message':'Redundanz eingeschränkt: '+' · '.join(degraded),'issues':degraded}
    if nodes and vrrp:
        return {'status':'HEALTHY','message':'Cluster vollständig funktions- und failoverbereit','issues':[]}
    return {'status':'UNKNOWN','message':'Clusterzustand kann nicht bestimmt werden','issues':[]}

def poll():
    c=cfg(); ns={n['name']:poll_node(n) for n in c.get('nodes',[])}; vs=[]
    for v in c.get('vrrp',[]):
        owners=[name for name in v.get('nodes',[]) if v['vip'] in ns.get(name,{}).get('addresses',[])]
        master=owners[0] if len(owners)==1 else ('MULTIPLE' if len(owners)>1 else None)
        record(v['name'],master or 'NONE')
        metrics=vrrp_metrics(v['name'])
        roles={name:('MASTER' if name==master else 'BACKUP') for name in v.get('nodes',[])}
        vs.append({**v,'master':master,'healthy':len(owners)==1,'roles':roles,**metrics})
    health=cluster_health(ns,vs)
    with lock: cache.update(nodes=ns,vrrp=vs,cluster=health,updated=datetime.now().isoformat(timespec='seconds'))

def loop():
    while True:
        try: poll()
        except Exception as e: print('poll error',e,flush=True)
        time.sleep(max(2,int(cfg().get('refresh_seconds',5))))

@app.route('/')
def index(): return render_template('index.html')
@app.route('/api/status')
def status():
    with lock: return jsonify(cache)
@app.route('/api/history')
def history():
    with sqlite3.connect(DB) as c:
        rows=c.execute('SELECT ts,name,old_master,new_master FROM events ORDER BY id DESC LIMIT 50').fetchall()
    result=[]
    for r in rows:
        old,new=r[2],r[3]
        kind='LOST' if new=='NONE' else ('RECOVERED' if old=='NONE' else 'FAILOVER')
        result.append({'ts':r[0],'name':r[1],'old':old,'new':new,'type':kind})
    return jsonify(result)

@app.route('/healthz')
def healthz(): return {'ok':True}

db_init(); poll()
threading.Thread(target=loop,daemon=True).start()
