"""Portable English data-research view for the evidence explorer."""
SECTION='''<section id="research"><span class="tag">04 / DATA RESEARCH</span><h2>Ten training attempts, every outcome retained</h2><p>Each researcher completed five data-selection and augmentation attempts. The student was fixed at Qwen3.5-4B, with a fresh LoRA adapter for each attempt. Action validity and task success are separate measurements.</p><div class="toolbar"><select id="researcher" aria-label="Select researcher"></select><select id="researchMetric" aria-label="Select metric"><option value="reward">Strict task reward</option><option value="valid_action_rate">Valid action rate</option></select></div><p id="researchSummary" class="legend"></p><svg id="researchPlot" viewBox="0 0 900 240" role="img" aria-label="Per-attempt research results" style="width:100%;background:white"></svg><p class="legend">Crosses indicate unavailable scores. Orange points show partial-prefix action validity before an interruption. Missing scores are never treated as zero. Select a round to inspect its recorded hypothesis.</p><div class="scroll"><table><thead><tr><th>Round</th><th>Training tokens</th><th>Reward</th><th>Valid actions</th><th>Promotion</th></tr></thead><tbody id="researchRows"></tbody></table></div><details open><summary>Research hypothesis</summary><p id="researchHypothesis"></p></details><p id="researchFinal"></p><p class="legend">Final repetitions share one task, seed and temperature. They check execution stability, not task diversity. There is no non-recursive search control or sustained RSI claim.</p></section>'''
SCRIPT='''
const campaigns=D.data_campaigns||[];
function svgElement(name,attrs,text){const e=document.createElementNS('http://www.w3.org/2000/svg',name);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e}
function renderResearch(){
 const r=campaigns[Number($('#researcher').value)];if(!r)return;
 const valid=r.attempts.filter(x=>x.evaluation.status==='scored').length;
 $('#researchSummary').textContent=`${r.researcher} | ${r.training_tokens.toLocaleString()} scheduled training tokens | ${valid} scored / ${r.attempts.length-valid} infrastructure-invalid | Selected: ${r.selection?.selected_baseline?'base model':'attempt '+r.selection?.selected_attempt} | Audit: ${r.audit_pass?'pass':'fail'}`;
 const plot=$('#researchPlot');plot.replaceChildren();const metric=$('#researchMetric').value;
 for(const y of [0,.5,1]){const yy=175-y*125;plot.append(svgElement('line',{x1:70,y1:yy,x2:840,y2:yy,stroke:'#bfcfc9'}));plot.append(svgElement('text',{x:18,y:yy+5,fill:'#5d7479','font-size':13},Math.round(y*100)+'%'))}
 plot.append(svgElement('text',{x:18,y:202,fill:'#a35629','font-size':12},'N/A'));
 $('#researchRows').replaceChildren();
 for(const [i,a] of r.attempts.entries()){
  const x=140+i*160;const v=a.evaluation[metric];plot.append(svgElement('text',{x,y:230,fill:'#5d7479','font-size':13,'text-anchor':'middle'},'Round '+a.attempt));
  if(v===null||v===undefined){plot.append(svgElement('path',{d:`M ${x-6} 191 L ${x+6} 203 M ${x-6} 203 L ${x+6} 191`,stroke:'#a35629','stroke-width':2}));}
  else {const dot=svgElement('circle',{cx:x,cy:175-v*125,r:6,fill:a.evaluation.status==='scored'?'#006b5b':'#a35629'});dot.append(svgElement('title',{},`Round ${a.attempt}: ${Math.round(v*1000)/10}%`));plot.append(dot)}
  const row=document.createElement('tr');const td=cell(row,'');const button=document.createElement('button');button.textContent=String(a.attempt);button.setAttribute('aria-label','Inspect round '+a.attempt);button.onclick=()=>$('#researchHypothesis').textContent=a.hypothesis;td.append(button);
  cell(row,a.training_tokens.toLocaleString());cell(row,a.evaluation.reward??'Unscored',a.evaluation.reward===null?'muted':a.evaluation.reward>0?'pass':'fail');cell(row,a.evaluation.valid_action_rate==null?'N/A':(100*a.evaluation.valid_action_rate).toFixed(1)+'%');cell(row,a.promoted?'Promoted':'Not promoted');$('#researchRows').append(row);
 }
 $('#researchHypothesis').textContent=r.attempts[0]?.hypothesis||'Unavailable';
 const scores=r.final_tests.map(x=>x.status==='scored'?String(x.reward):x.status==='infrastructure_error'?'Infrastructure error':'Pending');
 $('#researchFinal').textContent=`Original final executions: ${scores.join(' / ')}. ${r.final_avg===null?'No complete three-run mean: original executions include infrastructure errors.':'Three-execution mean: '+r.final_avg+'.'}`;
}
campaigns.forEach((r,i)=>{const o=document.createElement('option');o.value=i;o.textContent=r.researcher;$('#researcher').append(o)});
$('#researcher').onchange=renderResearch;$('#researchMetric').onchange=renderResearch;renderResearch();
'''

SECTION=SECTION.replace('</section>','''<details><summary>Separately versioned journaled recovery</summary><p>These executions reuse the original student, task, observer and verifier with durable-command transport. They do not overwrite original failures or count as new training attempts.</p><div class="scroll"><table><thead><tr><th>Execution</th><th>Role</th><th>Status</th><th>Reward</th></tr></thead><tbody id="recoveryRows"></tbody></table></div></details></section>''')
SCRIPT+='''
for(const r of D.journal_recovery?.runs||[]){const row=document.createElement('tr');cell(row,r.run);cell(row,r.run.startsWith('shared-final')?'Base-model stability':'Candidate replay');cell(row,r.evaluation.status);cell(row,r.evaluation.reward??'Unscored');$('#recoveryRows').append(row)}
'''
