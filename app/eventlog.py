import math, sqlite3, threading, time
from vrrp_events import classify_vrrp_event
from datetime import datetime
from flask import Blueprint, jsonify, render_template, request
bp=Blueprint('eventlog',__name__);_core=None;_started=False
def _now():return datetime.now().isoformat(timespec='seconds')
def _init_db():
    with sqlite3.connect(_core.DB) as c:c.execute('CREATE TABLE IF NOT EXISTS system_events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, category TEXT NOT NULL, subject TEXT NOT NULL, event_type TEXT NOT NULL, detail TEXT)');c.execute('CREATE INDEX IF NOT EXISTS idx_system_events_id ON system_events(id DESC)');c.execute('CREATE TABLE IF NOT EXISTS eventlog_meta (key TEXT PRIMARY KEY, value TEXT)')
def _record(category,subject,event_type,detail=None):
    with sqlite3.connect(_core.DB) as c:c.execute('INSERT INTO system_events(ts,category,subject,event_type,detail) VALUES(?,?,?,?,?)',(_now(),category,subject,event_type,detail))
def _watch():
    previous={};initialized=False
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
def _auth():return bool(_core.session.get('authenticated'))
def _csrf():return _core.csrf_ok()
def _all_events():
    with sqlite3.connect(_core.DB) as c:
        sys = c.execute(
            '''
            SELECT id,ts,category,subject,event_type,detail
            FROM system_events
            '''
        ).fetchall()

        cutoff = (
            c.execute(
                "SELECT value FROM eventlog_meta WHERE key='vrrp_cutoff'"
            ).fetchone()
            or [None]
        )[0]

        fail = c.execute(
            '''
            SELECT id,ts,name,old_master,new_master
            FROM events
            WHERE (? IS NULL OR ts>?)
            ''',
            (cutoff, cutoff)
        ).fetchall()

    out = [
        {
            'key': f's-{r[0]}',
            'ts': r[1],
            'category': r[2],
            'subject': r[3],
            'type': r[4],
            'detail': r[5],
        }
        for r in sys
    ]

    for event_id, ts, name, old, new in fail:
        out.append({
            'key': f'v-{event_id}',
            'ts': ts,
            'category': 'VRRP',
            'subject': name,
            'type': classify_vrrp_event(old, new),
            'detail': f'{old} → {new}',
        })

    out.sort(
        key=lambda x: (x['ts'], x['key']),
        reverse=True
    )

    return out
def init_eventlog(core):
    global _core,_started
    _core=core;_init_db();core.app.register_blueprint(bp)
    if not _started:_started=True;threading.Thread(target=_watch,daemon=True).start()
@bp.get('/events')
def events_page():
    if not _auth():return _core.redirect(_core.url_for('login',next=request.path))
    return render_template('events.html',nodes=_core.cfg().get('nodes',[]),csrf=_core.session['csrf'])
@bp.get('/api/events')
def events():
    if not _auth():return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    try:limit=max(1,min(200,int(request.args.get('limit',10))))
    except ValueError:limit=10
    return jsonify(_all_events()[:limit])
@bp.get('/api/events/page')
def events_page_api():
    if not _auth():
        return jsonify({'ok': False, 'error': 'Nicht angemeldet'}), 401

    try:
        per_page = int(request.args.get('per_page', 20))
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        per_page, page = 20, 1

    if per_page not in {10, 20, 50, 100}:
        per_page = 20

    category = request.args.get('category', 'ALL').upper()

    if category not in {'ALL', 'VRRP', 'NODE', 'MAINTENANCE'}:
        category = 'ALL'

    items = _all_events()

    if category != 'ALL':
        items = [
            item for item in items
            if item.get('category') == category
        ]

    total = len(items)
    pages = max(1, math.ceil(total / per_page))
    page = min(page, pages)
    start = (page - 1) * per_page

    return jsonify({
        'items': items[start:start + per_page],
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages,
        'category': category,
    })
@bp.post('/api/events/clear')
def clear_events():
    if not _auth():return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    if not _csrf():return jsonify({'ok':False,'error':'Ungültiges CSRF-Token'}),403
    cutoff=_now()
    with sqlite3.connect(_core.DB) as c:count=c.execute('SELECT COUNT(*) FROM system_events').fetchone()[0];c.execute('DELETE FROM system_events');c.execute("INSERT INTO eventlog_meta(key,value) VALUES('vrrp_cutoff',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(cutoff,))
    try:_core.write_audit('events.clear','event-history','success',{'system_events_deleted':count,'vrrp_cutoff':cutoff})
    except Exception:pass
    return jsonify({'ok':True})
@bp.post('/api/availability/reset')
def reset_availability():
    if not _auth():return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    if not _csrf():return jsonify({'ok':False,'error':'Ungültiges CSRF-Token'}),403
    with _core.availability_lock,sqlite3.connect(_core.DB) as c:count=c.execute('SELECT COUNT(*) FROM availability_state').fetchone()[0];c.execute('DELETE FROM availability_state')
    try:_core.poll()
    except Exception:pass
    try:_core.write_audit('availability.reset','all-nodes','success',{'nodes_reset':count})
    except Exception:pass
    return jsonify({'ok':True})
