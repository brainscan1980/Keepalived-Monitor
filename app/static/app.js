const esc=s=>String(s??'–').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const statusClass=s=>({HEALTHY:'good',DEGRADED:'warn',CRITICAL:'bad',UNKNOWN:'unknown'}[s]||'unknown');
const fmtDate=s=>s?new Date(s).toLocaleString():'Noch kein Wechsel';
async function load(){try{
  const s=await (await fetch('/api/status',{cache:'no-store'})).json();
  const nodes=Object.values(s.nodes||{}), cluster=s.cluster||{status:'UNKNOWN',message:'Status unbekannt'};
  const clusterEl=document.querySelector('#cluster'), state=statusClass(cluster.status);
  clusterEl.className=`pill header-cluster cluster-${state}`;
  clusterEl.innerHTML=`<span class="${state}"><i class="dot"></i>${esc(cluster.status)}</span>`;
  clusterEl.title=cluster.message||'Status unbekannt';
  clusterEl.setAttribute('aria-label',`${cluster.status}: ${cluster.message||'Status unbekannt'}`);
  document.querySelector('#nodes').innerHTML=nodes.map(n=>{
    const ready=n.online&&n.keepalived==='active';
    return `<div class="card"><b>${esc(n.name)}</b><div class="${ready?'good':n.online?'warn':'bad'} node-state"><i class="dot"></i>${n.online?'ONLINE':'OFFLINE'} · Keepalived ${esc(n.keepalived).toUpperCase()}</div><div class="meta">${esc(n.host)}<br>${esc(n.uptime)}</div>${!ready?`<div class="issue">⚠ ${n.online?'Nicht failoverbereit':'Node nicht erreichbar'}</div>`:''}</div>`
  }).join('');
  document.querySelector('#vrrp').innerHTML=(s.vrrp||[]).map(v=>{
    const chain=(v.nodes||[]).map(n=>`${esc(n)} <small>${esc((v.roles||{})[n]||'BACKUP')}</small>`).join(' → ');
    return `<div class="row vrrp-row"><div><b>${esc(v.name)}</b><div class="meta">${chain}</div></div><span>${esc(v.vip)}</span><span class="${v.healthy?'good':'bad'}"><b>${esc(v.master||'KEIN MASTER')}</b><div class="meta">${v.healthy?'MASTER':'FEHLER'}</div></span><span><b>${v.failovers||0}</b> Wechsel<div class="meta">${fmtDate(v.last_change)}</div></span></div>`
  }).join('');
  document.querySelector('#updated').textContent='Letztes Update: '+(s.updated?new Date(s.updated).toLocaleString():'–');
  const h=await (await fetch('/api/history',{cache:'no-store'})).json();
  document.querySelector('#history').innerHTML=h.length?h.slice(0,15).map(x=>`<div class="row history-row"><span>${new Date(x.ts).toLocaleString()}</span><b>${esc(x.name)}</b><span>${esc(x.old)} → ${esc(x.new)}</span><span><span class="badge ${x.type==='LOST'?'bad':x.type==='RECOVERED'?'good':'warn'}">${esc(x.type)}</span></span></div>`).join(''):'<div class="card meta">Noch keine Failover-Ereignisse aufgezeichnet.</div>';
}catch(e){const clusterEl=document.querySelector('#cluster');clusterEl.className='pill header-cluster cluster-bad';clusterEl.innerHTML='<span class="bad"><i class="dot"></i>UNKNOWN</span>';clusterEl.title='Dashboard nicht erreichbar';clusterEl.setAttribute('aria-label','UNKNOWN: Dashboard nicht erreichbar')}}

const systemDark=window.matchMedia('(prefers-color-scheme: dark)');
const getTheme=()=>localStorage.getItem('theme')||'auto';
function applyTheme(mode=getTheme()){
  const dark=mode==='dark'||(mode==='auto'&&systemDark.matches);
  document.documentElement.classList.toggle('dark',dark);
  document.documentElement.dataset.theme=mode;
  document.querySelectorAll('[data-theme]').forEach(b=>b.classList.toggle('active',b.dataset.theme===mode));
  const meta=document.querySelector('meta[name="theme-color"]');
  if(meta)meta.content=dark?'#0c1118':'#f4f6f8';
}
document.querySelectorAll('[data-theme]').forEach(b=>b.addEventListener('click',()=>{localStorage.setItem('theme',b.dataset.theme);applyTheme(b.dataset.theme)}));
systemDark.addEventListener?.('change',()=>{if(getTheme()==='auto')applyTheme('auto')});
applyTheme();
setInterval(load,5000);load();if('serviceWorker'in navigator)navigator.serviceWorker.register('/static/service-worker.js');
