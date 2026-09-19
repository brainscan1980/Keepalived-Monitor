const esc=s=>String(s??'–').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const eventClass=t=>
  ['NODE DOWN','VRRP LOST','LOST','NO_MASTER','SPLIT_BRAIN'].includes(t)?'bad':
  ['RECOVERED','VRRP RECOVERED','RECOVERY','NORMALIZED','MAINTENANCE END'].includes(t)?'good':
  t==='MAINTENANCE START'?'maintenance':
  t==='FAILOVER'?'warn':
  'warn';
const eventLabel=t=>({
    FAILOVER:'MASTER-Wechsel',
    NO_MASTER:'Kein MASTER',
    SPLIT_BRAIN:'Split-Brain',
    RECOVERY:'MASTER wiederhergestellt',
    NORMALIZED:'Split-Brain behoben'
}[t]||t);
function initSidebar(){
    const shell=document.querySelector('.app-shell'),
        collapse=document.querySelector('#sidebarCollapse'),
        menu=document.querySelector('#mobileMenu'),
        overlay=document.querySelector('#sidebarOverlay');

    const desktop=()=>innerWidth>900;

    if(
        desktop() &&
        localStorage.getItem('sidebarCollapsed')==='1'
    ){
        shell.classList.add('sidebar-collapsed');
    }

    collapse?.addEventListener('click',()=>{
        shell.classList.toggle('sidebar-collapsed');

        localStorage.setItem(
            'sidebarCollapsed',
            shell.classList.contains('sidebar-collapsed')?'1':'0'
        );
    });

    const mobile=o=>{
        shell.classList.toggle('sidebar-open',o);
        menu.textContent=o?'✕':'☰';
    };

    menu?.addEventListener('click',()=>{
        mobile(!shell.classList.contains('sidebar-open'));
    });

    overlay?.addEventListener('click',()=>{
        mobile(false);
    });
}
const systemDark=matchMedia('(prefers-color-scheme: dark)'),getTheme=()=>localStorage.getItem('theme')||'auto';function applyTheme(m=getTheme()){document.documentElement.classList.toggle('dark',m==='dark'||(m==='auto'&&systemDark.matches));document.querySelectorAll('[data-theme]').forEach(b=>b.classList.toggle('active',b.dataset.theme===m))}document.querySelectorAll('[data-theme]').forEach(b=>b.onclick=()=>{localStorage.setItem('theme',b.dataset.theme);applyTheme(b.dataset.theme)});initSidebar();applyTheme();
let page=1;async function loadEvents(){const perPage=Number(document.querySelector('#perPage').value),category=document.querySelector('#eventCategory').value,list=document.querySelector('#eventsList');list.innerHTML='<div class="meta">Ereignisse werden geladen…</div>';try{const r=await fetch(`/api/events/page?page=${page}&per_page=${perPage}&category=${encodeURIComponent(category)}`,{cache:'no-store'}),j=await r.json();if(!r.ok)throw new Error(j.error||`HTTP ${r.status}`);page=j.page;list.innerHTML=j.items.length?j.items.map(x=>`<div class="row history-row"><span>${esc(new Date(x.ts).toLocaleString())}</span><b>${esc(x.subject)}</b><span>${esc(x.detail||x.category)}</span><span><span class="badge ${eventClass(x.type)}">${esc(eventLabel(x.type))}</span></span></div>`).join(''):'<div class="meta"><b>Noch keine Ereignisse vorhanden.</b><br>Neue Node-, Wartungs- und VRRP-Ereignisse erscheinen automatisch hier.</div>';document.querySelector('#pageInfo').textContent=`Seite ${j.page} von ${j.pages} · ${j.total} Einträge`;document.querySelector('#prevPage').disabled=j.page<=1;document.querySelector('#nextPage').disabled=j.page>=j.pages}catch(e){list.innerHTML=`<div class="meta bad">Ereignisse konnten nicht geladen werden: ${esc(e.message)}</div>`}}
document.querySelector('#perPage').onchange=()=>{page=1;loadEvents()};document.querySelector('#eventCategory').onchange=()=>{page=1;loadEvents()};document.querySelector('#prevPage').onclick=()=>{if(page>1){page--;loadEvents()}};document.querySelector('#nextPage').onclick=()=>{page++;loadEvents()};document.querySelector('#clearEvents').onclick=async()=>{if(!confirm('Ereignis-Historie wirklich löschen? Node-, Wartungs- und VRRP-Ereignisse werden dauerhaft entfernt. Verfügbarkeits- und Benachrichtigungsdaten bleiben erhalten.'))return;const b=document.querySelector('#clearEvents'),res=document.querySelector('#eventsResult');b.disabled=true;try{const r=await fetch('/api/events/clear',{method:'POST',headers:{'X-CSRF-Token':CSRF_TOKEN}}),j=await r.json();res.textContent=j.ok?'✓ Ereignis-Historie gelöscht.':`✕ ${j.error||'Löschen fehlgeschlagen'}`;res.className=`action-result ${j.ok?'good':'bad'}`;if(j.ok){page=1;await loadEvents()}}finally{b.disabled=false}};loadEvents();
