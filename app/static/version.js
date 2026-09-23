(()=>{
  const brandingHref='/static/branding.css';
  if(!document.querySelector(`link[href="${brandingHref}"]`)){
    const link=document.createElement('link');
    link.rel='stylesheet';
    link.href=brandingHref;
    document.head.appendChild(link);
  }

  const brandedIconHref='/static/app-icon.svg';
  let brandedIcon=document.querySelector('link[rel="icon"][type="image/svg+xml"]');
  if(!brandedIcon){
    brandedIcon=document.createElement('link');
    brandedIcon.rel='icon';
    brandedIcon.type='image/svg+xml';
    document.head.prepend(brandedIcon);
  }
  brandedIcon.href=brandedIconHref;

  const el=document.querySelector('#appVersion'),update=document.querySelector('#updateAvailable');
  if(!el)return;

  const repo='brainscan1980/Keepalived-Monitor',cacheKey='keepalivedMonitorUpdateCheck',ttl=6*60*60*1000,clean=v=>String(v||'').trim().replace(/^v/i,''),parts=v=>clean(v).split(/[.-]/).map(x=>/^\d+$/.test(x)?Number(x):x),newer=(a,b)=>{const x=parts(a),y=parts(b),n=Math.max(x.length,y.length);for(let i=0;i<n;i++){const p=x[i]??0,q=y[i]??0;if(typeof p==='number'&&typeof q==='number'){if(p!==q)return p>q}else{const c=String(p).localeCompare(String(q));if(c)return c>0}}return false};

  async function latest(current){
    try{
      const cached=JSON.parse(localStorage.getItem(cacheKey)||'null');
      if(cached&&Date.now()-cached.ts<ttl)return cached.tag;
      const r=await fetch(`https://api.github.com/repos/${repo}/releases/latest`,{headers:{Accept:'application/vnd.github+json'}});
      if(!r.ok)throw new Error(`GitHub ${r.status}`);
      const j=await r.json(),tag=j.tag_name||'';
      localStorage.setItem(cacheKey,JSON.stringify({ts:Date.now(),tag}));
      return tag;
    }catch{return ''}
  }

  async function init(){
    try{
      const r=await fetch('/static/VERSION',{cache:'no-store'});
      if(!r.ok)throw new Error('VERSION');
      const current=(await r.text()).trim();
      el.textContent=`v${clean(current)}`;
      el.title=`Installierte Version: v${clean(current)}`;
      const tag=await latest(current);
      if(tag&&newer(tag,current)&&update){
        update.hidden=false;
        update.href=`https://github.com/${repo}/releases/latest`;
        update.title=`Neue Version ${tag} verfügbar`;
      }
    }catch{
      el.textContent='Version unbekannt';
    }
  }

  init();
})();
