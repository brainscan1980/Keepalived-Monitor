import sqlite3, threading, time
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request

bp=Blueprint('statistics',__name__)
_core=None
_started=False

# Historical samples are intentionally stored separately from the cumulative
# availability_state table. One compact sample per minute is enough for the
# 24h/7d/30d dashboard views and keeps the database small.
SAMPLE_INTERVAL=60
RETENTION_DAYS=32


def _now():
    return datetime.now()


def _init_db():
    with sqlite3.connect(_core.DB) as c:
        c.execute('''CREATE TABLE IF NOT EXISTS statistics_samples (
            ts TEXT NOT NULL,
            node TEXT NOT NULL,
            online INTEGER NOT NULL,
            keepalived_active INTEGER NOT NULL,
            maintenance INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(ts,node)
        )''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_statistics_samples_node_ts ON statistics_samples(node,ts)')
        c.execute('''CREATE TABLE IF NOT EXISTS statistics_vrrp_samples (
            ts TEXT NOT NULL,
            name TEXT NOT NULL,
            master TEXT,
            healthy INTEGER NOT NULL,
            PRIMARY KEY(ts,name)
        )''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_statistics_vrrp_name_ts ON statistics_vrrp_samples(name,ts)')


def _minute_stamp(now=None):
    now=now or _now()
    return now.replace(second=0,microsecond=0).isoformat(timespec='minutes')


def _sample_once(now=None):
    stamp=_minute_stamp(now)
    with _core.lock:
        nodes={k:dict(v) for k,v in (_core.cache.get('nodes') or {}).items()}
        vrrp=[dict(v) for v in (_core.cache.get('vrrp') or [])]
    if not nodes and not vrrp:
        return
    with sqlite3.connect(_core.DB) as c:
        for name,n in nodes.items():
            c.execute('INSERT OR REPLACE INTO statistics_samples(ts,node,online,keepalived_active,maintenance) VALUES(?,?,?,?,?)',(
                stamp,name,1 if n.get('online') else 0,1 if n.get('keepalived')=='active' else 0,
                1 if (n.get('maintenance') or {}).get('active') else 0))
        for v in vrrp:
            c.execute('INSERT OR REPLACE INTO statistics_vrrp_samples(ts,name,master,healthy) VALUES(?,?,?,?)',(
                stamp,v.get('name'),v.get('master'),1 if v.get('healthy') else 0))
        cutoff=(_now()-timedelta(days=RETENTION_DAYS)).isoformat(timespec='minutes')
        c.execute('DELETE FROM statistics_samples WHERE ts<?',(cutoff,))
        c.execute('DELETE FROM statistics_vrrp_samples WHERE ts<?',(cutoff,))


def _watch():
    while True:
        try:_sample_once()
        except Exception as e:print('statistics sampler error',e,flush=True)
        time.sleep(SAMPLE_INTERVAL)


def _auth():
    return bool(_core.session.get('authenticated'))


def _window_hours(value):
    return {'24h':24,'7d':168,'30d':720}.get(value,24)


def _node_stats(since):
    with sqlite3.connect(_core.DB) as c:
        rows=c.execute('''SELECT node,COUNT(*),
            SUM(CASE WHEN maintenance=0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN maintenance=0 AND online=1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN maintenance=0 AND keepalived_active=1 THEN 1 ELSE 0 END)
            FROM statistics_samples WHERE ts>=? GROUP BY node ORDER BY node''',(since,)).fetchall()
    out=[]
    for name,total,monitored,online,keep in rows:
        monitored=int(monitored or 0);online=int(online or 0);keep=int(keep or 0)
        out.append({'name':name,'samples':int(total or 0),'monitored_samples':monitored,
                    'availability':round(online/monitored*100,3) if monitored else None,
                    'keepalived_availability':round(keep/monitored*100,3) if monitored else None})
    return out


def _vrrp_stats(since):
    with sqlite3.connect(_core.DB) as c:
        rows=c.execute('SELECT name,ts,master,healthy FROM statistics_vrrp_samples WHERE ts>=? ORDER BY name,ts',(since,)).fetchall()
    grouped={}
    for name,ts,master,healthy in rows:grouped.setdefault(name,[]).append((ts,master,bool(healthy)))
    out=[]
    for name,samples in grouped.items():
        healthy=sum(1 for _,_,ok in samples if ok);failovers=0;previous=None
        for _,master,ok in samples:
            if ok and master and master not in {'NONE','MULTIPLE'}:
                if previous is not None and master!=previous:failovers+=1
                previous=master
        out.append({'name':name,'samples':len(samples),'healthy_percent':round(healthy/len(samples)*100,3) if samples else None,'failovers':failovers,'current_master':samples[-1][1] if samples else None})
    return out


def init_statistics(core):
    global _core,_started
    _core=core
    _init_db()
    core.app.register_blueprint(bp)
    if not _started:
        _started=True
        threading.Thread(target=_watch,daemon=True).start()


@bp.get('/api/statistics')
def statistics_api():
    if not _auth():return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    window=request.args.get('window','24h')
    if window not in {'24h','7d','30d'}:return jsonify({'ok':False,'error':'Ungültiges Zeitfenster'}),400
    hours=_window_hours(window);since_dt=_now()-timedelta(hours=hours);since=since_dt.isoformat(timespec='minutes')
    with sqlite3.connect(_core.DB) as c:
        first_node=(c.execute('SELECT MIN(ts) FROM statistics_samples WHERE ts>=?',(since,)).fetchone() or [None])[0]
        first_vrrp=(c.execute('SELECT MIN(ts) FROM statistics_vrrp_samples WHERE ts>=?',(since,)).fetchone() or [None])[0]
    first=min([x for x in (first_node,first_vrrp) if x],default=None)
    return jsonify({'window':window,'hours':hours,'since':since,'first_sample':first,'sample_interval_seconds':SAMPLE_INTERVAL,'nodes':_node_stats(since),'vrrp':_vrrp_stats(since)})
