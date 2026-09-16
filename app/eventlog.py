import sqlite3, threading, time
from datetime import datetime
from flask import Blueprint, jsonify, request

bp=Blueprint('eventlog',__name__)
_core=None
_started=False

def _now():return datetime.now().isoformat(timespec='seconds')

def _init_db():
    with sqlite3.connect(_core.DB) as c:
        c.execute('CREATE TABLE IF NOT EXISTS system_events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, category TEXT NOT NULL, subject TEXT NOT NULL, event_type TEXT NOT NULL, detail TEXT)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_system_events_id ON system_events(id DESC)')

def _record(category,subject,event_type,detail=None):
    with sqlite3.connect(_core.DB) as c:c.execute('INSERT INTO system_events(ts,category,subject,event_type,detail) VALUES(?,?,?,?,?)',(_now(),category,subject,event_type,detail))

def _watch():
    previous={}
    initialized=False
    while True:
        try:
            with _core.lock:nodes={k:dict(v) for k,v in (_core.cache.get('nodes') or {}).items()}
            current={name:{'online':bool(n.get('online')),'maintenance':bool((n.get('maintenance') or {}).get('active'))} for name,n in nodes.items()}
            if initialized:
                for name,state in current.items():
                    old=previous.get(name)
                    if not old:continue
                    if old['online']!=state['online']:_record('NODE',name,'RECOVERED' if state['online'] else 'NODE DOWN','Node wieder erreichbar' if state['online'] else 'Node nicht erreichbar')
                    if old['maintenance']!=state['maintenance']:_record('MAINTENANCE',name,'MAINTENANCE END' if not state['maintenance'] else 'MAINTENANCE START','Wartungsmodus beendet' if not state['maintenance'] else 'Wartungsmodus aktiviert')
            elif current:initialized=True
            previous=current
        except Exception as e:print('event watcher error',e,flush=True)
        time.sleep(2)

def init_eventlog(core):
    global _core,_started
    _core=core;_init_db()
    core.app.register_blueprint(bp)
    if not _started:
        _started=True;threading.Thread(target=_watch,daemon=True).start()

@bp.get('/api/events')
def events():
    if not _core.session.get('authenticated'):return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    try:limit=max(1,min(200,int(request.args.get('limit',50))))
    except ValueError:limit=50
    with sqlite3.connect(_core.DB) as c:
        sys=c.execute('SELECT ts,category,subject,event_type,detail FROM system_events ORDER BY id DESC LIMIT ?',(limit,)).fetchall()
        fail=c.execute('SELECT ts,name,old_master,new_master FROM events ORDER BY id DESC LIMIT ?',(limit,)).fetchall()
    out=[{'ts':r[0],'category':r[1],'subject':r[2],'type':r[3],'detail':r[4]} for r in sys]
    for ts,name,old,new in fail:
        typ='VRRP LOST' if new=='NONE' else ('VRRP RECOVERED' if old=='NONE' else 'FAILOVER')
        detail=f'{old} → {new}'
        out.append({'ts':ts,'category':'VRRP','subject':name,'type':typ,'detail':detail})
    out.sort(key=lambda x:x['ts'],reverse=True)
    return jsonify(out[:limit])
