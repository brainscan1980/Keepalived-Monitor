/* Rich preflight and result renderers loaded after settings.js. */
(function(){
  const h=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  window.renderFailoverPreflight=function(j){
    const out=document.querySelector('#failoverPreflight');if(!out)return false;
    const masters=j.summary?.masters||[], allSafe=!!(j.safe_to_test&&j.summary?.blocked===0&&masters.length===1);
    const instances=(j.instances||[]).map(i=>{
      const backups=(i.ready_backups||[]).join(', ')||'Kein betriebsbereiter Backup';
      const reasons=(i.blocked_reasons||[]).map(r=>`<div class="failover-preflight-reason">${h(r)}</div>`).join('');
      return `<div class="failover-preflight-row ${i.allowed?'ok':'fail'}"><div class="failover-preflight-mark">${i.allowed?'✓':'✕'}</div><div class="failover-preflight-info"><div class="failover-preflight-name">${h(i.name)} <span>${h(i.vip||'–')}</span></div><div class="failover-preflight-meta"><span>MASTER <b>${h(i.master||'–')}</b></span><span>Backup <b>${h(backups)}</b></span></div>${reasons}</div><div class="failover-preflight-state ${i.allowed?'ok':'fail'}">${i.allowed?'Bereit':'Blockiert'}</div></div>`;
    }).join('');
    out.className='action-result';
    out.innerHTML=`<div class="failover-preflight-panel ${allSafe?'success':'failure'}"><div class="failover-preflight-head"><div class="failover-result-icon">${allSafe?'✓':'✕'}</div><div class="failover-preflight-heading"><div class="failover-result-title">${allSafe?'Preflight erfolgreich':'Preflight blockiert'}</div><div class="failover-result-sub">${h(j.summary?.testable||0)}/${h(j.summary?.total||0)} VRRP-Instanzen testbar · ${h(j.summary?.blocked||0)} blockiert</div></div><div class="failover-preflight-master"><span>Gemeinsamer MASTER</span><b>${masters.length===1?h(masters[0]):'Nicht eindeutig'}</b></div></div><div class="failover-preflight-body"><div class="failover-result-section-title">VRRP-Instanzen</div><div class="failover-preflight-list">${instances||'<div class="meta">Keine VRRP-Instanzen vorhanden.</div>'}</div><div class="failover-preflight-summary">${allSafe?'✓ Der Cluster erfüllt alle Voraussetzungen für einen kontrollierten Failover-Test.':'✕ Der Failover-Test kann mit dem aktuellen Clusterzustand nicht sicher gestartet werden.'}</div></div></div>`;
    return allSafe;
  };

  window.renderFailoverResult=function(j){
    const out=document.querySelector('#failoverTestResult');if(!out)return;
    const success=!!j.ok, failover=j.failover||{}, recovery=j.recovery||{};
    const steps=(j.steps||[]).map(s=>`<div class="failover-result-step ${s.ok?'ok':'fail'}"><span class="mark">${s.ok?'✓':'✕'}</span><span>${h(s.message)}</span></div>`).join('');
    const instances=(failover.instances||[]).map(i=>`<div class="failover-instance-row"><div class="failover-instance-name">${h(i.name)}</div><div class="failover-instance-route">${h(i.old_master||'–')} → ${h(i.new_master||'–')}</div><div class="failover-instance-state ${i.moved?'ok':'fail'}">${i.moved?'✓ Übernommen':'✕ Fehlgeschlagen'}</div></div>`).join('');
    const timing=[];if(failover.seconds!=null)timing.push(`Failover ${h(failover.seconds)} s`);if(recovery.seconds!=null)timing.push(`Cluster-Erholung ${h(recovery.seconds)} s`);
    out.className='action-result';
    out.innerHTML=`<div class="failover-result-panel ${success?'success':'failure'}"><div class="failover-result-head"><div class="failover-result-icon">${success?'✓':'✕'}</div><div><div class="failover-result-title">${success?'Failover-Test erfolgreich':'Failover-Test nicht vollständig erfolgreich'}</div><div class="failover-result-sub">MASTER: ${h(j.master||'–')}${timing.length?' · '+timing.join(' · '):''}</div></div></div><div class="failover-result-body"><div class="failover-result-section-title">Testablauf</div><div class="failover-result-steps">${steps||'<div class="meta">Keine Testschritte vorhanden.</div>'}</div>${instances?`<div class="failover-result-section"><div class="failover-result-section-title">VRRP-Übernahme</div><div class="failover-instance-grid">${instances}</div></div>`:''}<div class="failover-result-summary">${success?'✓ Automatischer Failover-Test erfolgreich abgeschlossen.':h(j.message||'Failover-Test nicht vollständig erfolgreich.')}</div>${j.error?`<div class="failover-result-error"><b>Fehler:</b> ${h(j.error)}</div>`:''}</div></div>`;
    out.scrollIntoView({behavior:'smooth',block:'nearest'});
  };
})();