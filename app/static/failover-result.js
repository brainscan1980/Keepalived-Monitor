/* Rich result renderer loaded after settings.js. */
(function(){
  const h=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
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