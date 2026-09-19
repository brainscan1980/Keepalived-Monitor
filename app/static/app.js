const esc=s=>String(s??'–').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const statusClass=s=>({HEALTHY:'good',DEGRADED:'warn',CRITICAL:'bad',UNKNOWN:'unknown'}[s]||'unknown');
const statusLabel=s=>({HEALTHY:'Cluster OK',DEGRADED:'Prüfung erforderlich',CRITICAL:'Kritischer Zustand',UNKNOWN:'Status unbekannt'}[s]||'Status unbekannt');
const validationClass=s=>({OK:'good',WARNING:'warn',ERROR:'bad',UNKNOWN:'unknown'}[s]||'unknown');
const validationLabel=s=>({OK:'OK',WARNING:'WARNUNG',ERROR:'FEHLER',UNKNOWN:'UNBEKANNT'}[s]||'UNBEKANNT');
const clusterLightStyle=s=>({good:'background:#ccebd9;border-color:#178a52;box-shadow:0 4px 14px #178a5224',warn:'background:#ffed9a;border-color:#b58a00;box-shadow:0 4px 14px #b58a0024',bad:'background:#f7caca;border-color:#c53a3a;box-shadow:0 4px 14px #c53a3a24',unknown:'background:#dce1e6;border-color:#7a8491;box-shadow:0 4px 14px #7a849124'}[s]||'');
const fmtDate=s=>s?new Date(s).toLocaleString():'Noch kein Wechsel';
const fmtDuration=s=>{s=Math.max(0,Math.round(Number(s)||0));const d=Math.floor(s/86400);s%=86400;const h=Math.floor(s/3600);s%=3600;const m=Math.floor(s/60);if(d)return `${d} T ${h} Std.`;if(h)return `${h} Std. ${m} Min.`;if(m)return `${m} Min.`;return `${s} Sek.`};
const eventClass=t=>
  ['NODE DOWN','VRRP LOST','LOST','NO_MASTER','SPLIT_BRAIN'].includes(t)?'bad':
  ['RECOVERED','VRRP RECOVERED','RECOVERY','NORMALIZED','MAINTENANCE END'].includes(t)?'good':
  t==='MAINTENANCE START'?'maintenance':'warn';function initSidebar(){const shell=document.querySelector('.app-shell'),collapse=document.querySelector('#sidebarCollapse'),menu=document.querySelector('#mobileMenu'),overlay=document.querySelector('#sidebarOverlay');if(!shell)return;const desktop=()=>innerWidth>900;if(desktop()&&localStorage.getItem('sidebarCollapsed')==='1')shell.classList.add('sidebar-collapsed');if(collapse)collapse.title=shell.classList.contains('sidebar-collapsed')?'Sidebar ausklappen':'Sidebar einklappen';collapse?.addEventListener('click',()=>{shell.classList.toggle('sidebar-collapsed');localStorage.setItem('sidebarCollapsed',shell.classList.contains('sidebar-collapsed')?'1':'0');collapse.title=shell.classList.contains('sidebar-collapsed')?'Sidebar ausklappen':'Sidebar einklappen'});const setMobile=open=>{shell.classList.toggle('sidebar-open',open);menu?.setAttribute('aria-expanded',open?'true':'false');if(menu){menu.textContent=open?'✕':'☰';menu.title=open?'Menü schließen':'Menü öffnen'}};menu?.addEventListener('click',()=>setMobile(!shell.classList.contains('sidebar-open')));overlay?.addEventListener('click',()=>setMobile(false));document.querySelectorAll('.sidebar .nav-link').forEach(a=>a.addEventListener('click',()=>{if(!desktop())setMobile(false)}));addEventListener('resize',()=>{if(desktop())setMobile(false)})}
function renderClusterValidation(v){const el=document.querySelector('#clusterValidation');if(!el)return;if(!v){el.innerHTML='<div class="card meta unknown">Noch keine detaillierte Cluster-Prüfung verfügbar.</div>';return}const cls=validationClass(v.status),sum=v.summary||{},total=(v.instances||[]).length,headline=v.status==='OK'?'Cluster vollständig failoverbereit':v.status==='WARNING'?'Cluster funktionsfähig – Redundanz eingeschränkt':v.status==='ERROR'?'HA-Fehler erkannt':'Clusterzustand nicht vollständig bestimmbar';const instances=(v.instances||[]).map(i=>{const icls=validationClass(i.status),master=i.master==='MULTIPLE'?'MEHRERE MASTER':i.master||'KEIN MASTER',backups=Number(i.available_backups||0);const problems=(i.checks||[]).filter(c=>c.level!=='OK');const detail=problems.length?`<div class="validation-issues">${problems.map(c=>`<div class="validation-check ${validationClass(c.level)}"><span>${c.level==='ERROR'?'✕':c.level==='WARNING'?'⚠':'?'}</span><span>${esc(c.message)}</span></div>`).join('')}</div>`:'';return `<div class="validation-instance validation-${icls}"><div class="validation-instance-head"><div><b>${esc(i.name)}</b><div class="meta">VIP ${esc(i.vip)}</div></div><span class="validation-badge ${icls}"><i class="dot"></i>${validationLabel(i.status)}</span></div><div class="validation-facts"><span><small>MASTER</small><b>${esc(master)}</b></span><span><small>BACKUP</small><b>${backups} betriebsbereit</b></span></div>${detail}</div>`}).join('');el.innerHTML=`<div class="validation-summary validation-${cls}"><div><b class="validation-title"><span class="${cls}">${v.status==='OK'?'✓':v.status==='WARNING'?'⚠':v.status==='ERROR'?'✕':'?'}</span> ${esc(headline)}</b><div class="meta">${esc(v.message)}</div></div><div class="validation-counts"><span class="good">${sum.ok||0} OK</span>${sum.warning?`<span class="warn">${sum.warning} Warnung</span>`:''}${sum.error?`<span class="bad">${sum.error} Fehler</span>`:''}${sum.unknown?`<span class="unknown">${sum.unknown} unbekannt</span>`:''}<small>${total} VRRP-Instanz${total===1?'':'en'}</small></div></div><div class="validation-grid">${instances}</div>`}
async function load(){try{const s=await (await fetch('/api/status',{cache:'no-store'})).json();const nodes=Object.values(s.nodes||{}),cluster=s.cluster||{status:'UNKNOWN',message:'Status unbekannt'};const clusterEl=document.querySelector('#cluster'),state=statusClass(cluster.status);clusterEl.className=`pill header-cluster cluster-${state}`;clusterEl.style.cssText=document.documentElement.classList.contains('dark')?'':clusterLightStyle(state);clusterEl.innerHTML=`<span class="cluster-status-main ${state}"><i class="dot"></i>${esc(cluster.status)}</span><small class="cluster-status-sub">${esc(statusLabel(cluster.status))}</small>`;clusterEl.title=cluster.message||statusLabel(cluster.status);clusterEl.setAttribute('aria-label',`${cluster.status}: ${cluster.message||statusLabel(cluster.status)}`);document.querySelector('#nodes').innerHTML=nodes.map(n=>{const ready=n.online&&n.keepalived==='active',maintenance=!!n.maintenance?.active,url=`/node/${encodeURIComponent(n.name)}`,status=maintenance?'MAINTENANCE':`${n.online?'ONLINE':'OFFLINE'} · Keepalived ${esc(n.keepalived).toUpperCase()}`,cls=maintenance?'maintenance':ready?'good':n.online?'warn':'bad';return `<a class="card node-card-link ${maintenance?'maintenance-card-active':''}" href="${url}" aria-label="Statusseite von ${esc(n.name)} öffnen"><b>${esc(n.name)}</b><div class="${cls} node-state"><i class="dot"></i>${status}</div><div class="meta">${esc(n.host)}<br>${esc(n.uptime)}</div>${maintenance?`<div class="maintenance-note">Wartungsmodus · Alarmierung pausiert</div>`:!ready?`<div class="issue">⚠ ${n.online?'Nicht failoverbereit':'Node nicht erreichbar'}</div>`:''}</a>`}).join('');
const avEl=document.querySelector('#availability');try{const ar=await fetch('/api/availability',{cache:'no-store'}),a=ar.ok?await ar.json():[];avEl.innerHTML=a.length?a.map(x=>{const pct=x.availability==null?'–':`${Number(x.availability).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:3})} %`,cls=x.maintenance?'maintenance':x.availability==null?'unknown':x.availability>=99.9?'good':x.availability>=99?'warn':'bad';return `<div class="card"><b>${esc(x.name)}</b><div class="${cls} node-state"><i class="dot"></i>${esc(pct)}</div><div class="meta">Überwacht: ${esc(fmtDuration(x.monitored_seconds))}<br>Downtime: ${esc(fmtDuration(x.downtime_seconds))}<br>Ausfälle: <b>${esc(x.outages)}</b></div>${x.maintenance?'<div class="maintenance-note">Wartungszeit wird nicht gewertet</div>':x.current_down_since?`<div class="issue">⚠ Offline seit ${esc(new Date(x.current_down_since).toLocaleString())}</div>`:`<div class="meta">Messung seit ${esc(new Date(x.started_at).toLocaleString())}</div>`}</div>`}).join(''):'<div class="card meta">Die Verfügbarkeitsmessung wurde gerade gestartet. Nach den ersten Messintervallen erscheinen hier Werte.</div>'}catch(e){avEl.innerHTML='<div class="card meta bad">Verfügbarkeitsstatistik konnte nicht geladen werden.</div>'}
const vrrpEl=document.querySelector('#vrrp');

vrrpEl.innerHTML=(s.vrrp||[]).map(v=>{
    const chain=(v.nodes||[])
        .map(n=>`${esc(n)} <small>${esc((v.roles||{})[n]||'BACKUP')}</small>`)
        .join(' → ');

    const failovers=Number(v.failovers||0);
    const splitBrain=Number(v.split_brain||0);
    const noMaster=Number(v.no_master||0);
    const critical=splitBrain+noMaster;

    const criticalDetails=[
        splitBrain ? `<span class="bad"><b>${esc(splitBrain)}</b> Split-Brain</span>` : '',
        noMaster ? `<span class="bad"><b>${esc(noMaster)}</b> ohne MASTER</span>` : ''
    ].filter(Boolean).join(' · ');

    return `
        <div class="row vrrp-row">
            <div>
                <b>${esc(v.name)}</b>
                <div class="meta">${chain}</div>
            </div>

            <span>${esc(v.vip)}</span>

            <span class="${v.healthy?'good':'bad'}">
                <b>${esc(v.master||'KEIN MASTER')}</b>
                <div class="meta">${v.healthy?'MASTER':'FEHLER'}</div>
            </span>

            <span class="vrrp-events">
                <b>${esc(failovers)}</b> MASTER-Wechsel
                <div class="meta">
                    ${v.last_failover
                        ? `Letzter: ${esc(fmtDate(v.last_failover))}`
                        : 'Noch kein MASTER-Wechsel'}
                </div>

                ${critical
                    ? `<div class="vrrp-critical">${criticalDetails}</div>`
                    : '<div class="meta good">Keine kritischen VRRP-Ereignisse</div>'}
            </span>
        </div>
    `;
}).join('');

renderClusterValidation(cluster.validation);document.querySelector('#updated').textContent='Letztes Update: '+(s.updated?new Date(s.updated).toLocaleString():'–');let h=[];let hr=await fetch('/api/events?limit=10',{cache:'no-store'});if(hr.ok)h=await hr.json();else{hr=await fetch('/api/history',{cache:'no-store'});if(hr.ok)h=(await hr.json()).slice(0,10).map(x=>({ts:x.ts,subject:x.name,detail:`${x.old||'–'} → ${x.new||'–'}`,category:'VRRP',type:x.type}))}document.querySelector('#history').innerHTML=h.length?h.slice(0,10).map(x=>`<div class="row history-row"><span>${new Date(x.ts).toLocaleString()}</span><b>${esc(x.subject||x.name)}</b><span>${esc(x.detail||x.category||'VRRP')}</span><span><span class="badge ${eventClass(x.type)}">${esc(x.type)}</span></span></div>`).join(''):'<div class="card meta">Noch keine Ereignisse aufgezeichnet.</div>'}catch(e){const clusterEl=document.querySelector('#cluster');clusterEl.className='pill header-cluster cluster-bad';clusterEl.style.cssText=document.documentElement.classList.contains('dark')?'':clusterLightStyle('bad');clusterEl.innerHTML='<span class="cluster-status-main bad"><i class="dot"></i>UNKNOWN</span><small class="cluster-status-sub">Dashboard nicht erreichbar</small>';clusterEl.title='Dashboard nicht erreichbar'}}
const systemDark=window.matchMedia('(prefers-color-scheme: dark)'),getTheme=()=>localStorage.getItem('theme')||'auto';function applyTheme(mode=getTheme()){const dark=mode==='dark'||(mode==='auto'&&systemDark.matches);document.documentElement.classList.toggle('dark',dark);document.documentElement.dataset.theme=mode;document.querySelectorAll('[data-theme]').forEach(b=>b.classList.toggle('active',b.dataset.theme===mode));const meta=document.querySelector('meta[name="theme-color"]');if(meta)meta.content=dark?'#0c1118':'#f4f6f8';const clusterEl=document.querySelector('#cluster');if(clusterEl){const state=['good','warn','bad','unknown'].find(x=>clusterEl.classList.contains(`cluster-${x}`))||'unknown';clusterEl.style.cssText=dark?'':clusterLightStyle(state)}}document.querySelectorAll('[data-theme]').forEach(b=>b.addEventListener('click',()=>{localStorage.setItem('theme',b.dataset.theme);applyTheme(b.dataset.theme)}));systemDark.addEventListener?.('change',()=>{if(getTheme()==='auto')applyTheme('auto')});initSidebar();applyTheme();setInterval(load,5000);load();if('serviceWorker'in navigator)navigator.serviceWorker.register('/static/service-worker.js');