import { renderElement as renderFrozenElement } from '../vendor/production_core/core/universal_renderer.mjs';
import { prepareEngineeringChart, renderEngineeringChartSvg } from '../vendor/production_core/core/engineering_chart_engine.mjs';
import { prepareTimeline } from '../vendor/production_core/core/timeline_semantics_engine.mjs';
import { validateGraph } from '../vendor/production_core/core/graph_semantics_engine.mjs';

const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const slug=value=>String(value).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
const num=(v,fallback='—')=>v===null||v===undefined||v===''?fallback:esc(v);
const alignment=value=>['left','center','right'].includes(value)?value:'left';
const shell=(entry,body,eyebrow=null)=>{
  const showTitle=entry.showTitle===true||entry.show_title===true;
  const heading=showTitle?`<header><div><span class="engine-label">${esc(eyebrow||entry.engine.replace(/Engine|Composite|Layer|Infrastructure/g,''))}</span><h3 data-direct="title" title="Double-click to edit title">${esc(entry.title||entry.element)}</h3></div></header>`:'';
  return `<article class="gallery-card integrated-variant ${showTitle?'has-title':'title-hidden'} align-${alignment(entry.textAlign||entry.text_align)} engine-${slug(entry.engine)} variant-${slug(entry.element)}" data-element="${esc(entry.element)}" data-engine="${esc(entry.engine)}" data-variant="${slug(entry.element)}">${heading}<div class="card-body">${body}</div></article>`;
};

function metric(entry){
  const n=entry.element.toLowerCase(),value=num(entry.value, n.includes('capacity')?'1.42M':n.includes('rate')?'98.7%':'42.8'),unit=esc(entry.unit||'');
  if(n.includes('pair')) return shell(entry,`<div class="metric-pair"><div><span>Primary</span><b>${value}${unit}</b></div><div><span>Secondary</span><b>${num(entry.target,'38.4')}</b></div></div>`,'Metric');
  if(n.includes('strip')) return shell(entry,`<div class="metric-strip">${[['Yield','98.7%'],['Cycle','42.8m'],['Risk','Low']].map(([k,v])=>`<div><span>${k}</span><b>${v}</b></div>`).join('')}</div>`,'Metric');
  if(n.includes('target')) { const actual=num(entry.actual??entry.value,'42.8'),target=num(entry.target,'50'),variance=num(entry.variance,'−7.2'); return shell(entry,`<div class="target-metric"><div class="metric-value">${actual}${unit}</div><div class="target-track"><i style="width:72%"></i><em style="left:84%"></em></div><div class="metric-meta"><span>Target ${target}</span><span>Variance ${variance}</span></div></div>`,'Metric'); }
  if(n.includes('progress')) { const current=entry.current??entry.value??0,max=entry.max??100,pct=max===0?0:Math.max(0,Math.min(100,Number(current)/Number(max)*100||0)); return shell(entry,`<div class="metric-value">${num(current)}${unit}</div><div class="progress-hero"><i style="width:${pct}%"></i></div><div class="metric-meta"><span>${Math.round(pct)}% complete</span><span>Max ${num(max)}</span></div>`,'Metric'); }
  if(n.includes('confidence')) { const confidence=entry.confidence??entry.value??84,label=esc(entry.interpretation||(+confidence>=80?'High confidence':+confidence>=55?'Moderate confidence':'Low confidence')); return shell(entry,`<div class="confidence-wrap"><div class="metric-ring-small"><span>${num(confidence)}%</span></div><div><b>${label}</b><p>${esc(entry.context||'Independent signals summarized against configured confidence bands.')}</p></div></div>`,'Metric'); }
  if(n.includes('status')) return shell(entry,`<div class="status-hero"><i></i><div><b>On track</b><span>${value}${unit}</span></div></div><div class="metric-meta"><span>Within operating band</span></div>`,'Metric');
  if(n.includes('threshold')) { const warning=entry.warning??70,critical=entry.critical??90,current=entry.value??0,max=Math.max(Number(critical)||100,Number(current)||0,1),pos=Math.max(0,Math.min(100,(Number(current)||0)/max*100)); return shell(entry,`<div class="metric-value">${value}${unit}</div><div class="threshold-scale"><span></span><span></span><span></span><i style="left:${pos}%"></i></div><div class="metric-meta"><span>Watch ${num(warning)}</span><span>Critical ${num(critical)}</span></div>`,'Metric'); }
  if(n.includes('sparkline')) return shell(entry,`<div class="metric-value compact">${value}${unit}</div><svg class="metric-spark" viewBox="0 0 180 48"><path d="M3 39L32 31L61 34L90 19L119 25L148 13L177 9"/></svg><div class="metric-meta"><span>${num(entry.delta,'+6.4')}%</span><span>${esc(entry.period||'last 7 periods')}</span></div>`,'Metric');
  if(n.includes('ring')) { const max=Number(entry.max??100)||100,current=Number(entry.value??0)||0,pct=Math.max(0,Math.min(100,current/max*100)); return shell(entry,`<div class="metric-ring-large"><svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="38" class="chart-ring-bg"/><circle cx="50" cy="50" r="38" class="chart-ring" pathLength="100" stroke-dasharray="${pct} ${100-pct}" transform="rotate(-90 50 50)"/></svg><b>${num(entry.value,0)}${unit}</b></div><div class="metric-meta center"><span>${esc(entry.center_label||'Progress')}</span></div>`,'Metric'); }
  if(n.includes('ladder')) { const levels=Array.isArray(entry.levels)&&entry.levels.length?entry.levels:[['P90',52],['Median',42.8],['P10',31]]; return shell(entry,`<div class="metric-ladder">${levels.slice(0,5).map((x,i)=>{const label=Array.isArray(x)?x[0]:x.label,val=Array.isArray(x)?x[1]:x.value;return `<div class="l${i}"><span>${esc(label)}</span><b>${num(val)}</b></div>`;}).join('')}</div>`,'Metric'); }
  if(n.includes('metric + delta')) return shell(entry,`<div class="delta-metric"><b>${value}${unit}</b><span>▲ ${num(entry.delta,'6.4')}%</span><small>vs previous period</small></div>`,'Metric');
  if(n.includes('capacity')) { const current=Number(entry.current??entry.value??0)||0,capacity=Number(entry.capacity??100)||100,pct=Math.max(0,Math.min(100,current/capacity*100)); return shell(entry,`<div class="capacity-metric"><b>${num(entry.current??entry.value)}${unit}</b><div><i style="width:${pct}%"></i><em></em></div><span>${Math.round(pct)}% of ${num(entry.capacity,capacity)} capacity</span></div>`,'Metric'); }
  if(n.includes('rate')) { const basis=entry.denominator!=null?`${num(entry.numerator,'—')} / ${num(entry.denominator,'—')}`:value; return shell(entry,`<div class="rate-metric"><b>${basis}${unit}</b><i>↗</i><span>${esc(entry.period||'per period')}</span></div>`,'Metric'); }
  return shell(entry,`<div class="metric-value">${value}${unit}</div><div class="metric-meta"><span class="state good">▲ ${num(entry.delta,'6.4')}%</span><span>vs target</span></div><div class="meter"><span style="width:84%"></span></div>`,'Metric');
}

function comparison(entry){
  const n=entry.element.toLowerCase();
  if(n.includes('time compression')) return shell(entry,`<div class="time-compression-live"><div><i></i><i></i><i></i><i></i><b>188m</b></div><span>→</span><div class="short"><i></i><b>14m</b></div></div>`,'Comparison');
  if(n.includes('reduction')) return shell(entry,`<div class="reduction-visual"><div><b>${num(entry.before,'188')}</b><span>Before</span></div><i>↓ 92%</i><div><b>${num(entry.after,'14')}</b><span>After</span></div></div>`,'Comparison');
  if(n.includes('process simplification')) return shell(entry,`<div class="simplification-live"><div>${Array.from({length:6},()=>'<i></i>').join('')}</div><b>→</b><div>${Array.from({length:3},()=>'<i></i>').join('')}</div></div><p class="body-copy">Fewer handoffs, same outcome.</p>`,'Comparison');
  if(n.includes('transformation flow')) return shell(entry,`<div class="transform-flow"><span class="complex">7 steps</span><i>→</i><span class="simple">3 steps</span></div><p class="body-copy">Lower handoff count and clearer ownership.</p>`,'Comparison');
  if(n.includes('quality')) return shell(entry,`<div class="quality-shift"><span style="--v:62%">62%</span><span style="--v:91%">91%</span></div><div class="metric-meta"><span>Before</span><span>After</span></div>`,'Comparison');
  if(n.includes('as-is')) return shell(entry,`<div class="asis-tobe"><div><b>As-is</b><span>${num(entry.before,'Current')}</span></div><i>→</i><div><b>To-be</b><span>${num(entry.after,'Future')}</span></div></div>`,'Comparison');
  if(n.includes('before/after')) return shell(entry,`<div class="before-after-kpi"><div><small>Before</small><b>${num(entry.before,'62')}</b></div><div><small>After</small><b>${num(entry.after,'91')}</b><em>▲</em></div></div>`,'Comparison');
  if(n.includes('capability')) return shell(entry,`<div class="capability-shift"><span><i style="width:42%"></i></span><b>→</b><span><i style="width:78%"></i></span></div><div class="metric-meta"><span>Current capability</span><span>Target</span></div>`,'Comparison');
  if(n.includes('cost/capacity')) return shell(entry,`<div class="cost-capacity"><div><b>Cost</b><i style="height:68%"></i></div><div><b>Capacity</b><i style="height:88%"></i></div><span>Tradeoff</span></div>`,'Comparison');
  return shell(entry,`<div class="comparison"><div><span class="eyebrow">Before</span><b>${num(entry.before,'62%')}</b><small>Current state</small></div><span class="compare-arrow">→</span><div><span class="eyebrow">After</span><b>${num(entry.after,'91%')}</b><small>Target state</small></div></div>`,'Comparison');
}

function table(entry){
  const n=entry.element.toLowerCase();
  if(entry.dataset_id&&entry.customTable?.headers?.length) return shell(entry,`<div class="table-frame"><table><thead><tr>${entry.customTable.headers.slice(0,4).map((h,i)=>`<th data-direct="dataset-header:${i}" title="Double-click to rename">${esc(h)}</th>`).join('')}</tr></thead><tbody>${(entry.customTable.rows||[]).slice(0,5).map((row,r)=>`<tr>${entry.customTable.headers.slice(0,4).map((_,i)=>`<td data-direct="dataset-cell:${r}:${i}" title="Double-click to edit">${num(row[i],'')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`,'Table');
  if(n.includes('ranked')) return shell(entry,`<div class="rank-list">${[['01','Chamber A','92'],['02','Chamber C','87'],['03','Chamber B','71']].map(r=>`<div><b>${r[0]}</b><span>${r[1]}</span><em>${r[2]}</em></div>`).join('')}</div>`,'Table');
  if(n.includes('kpi')) return shell(entry,`<div class="kpi-table">${[['Yield','98.7%','good'],['Cycle','42.8m','good'],['Scrap','1.8%','warn']].map(r=>`<div><span>${r[0]}</span><b>${r[1]}</b><i class="${r[2]}"></i></div>`).join('')}</div>`,'Table');
  if(n.includes('action')) return shell(entry,`<div class="action-list">${[['Contain chamber','J. Kim','Today'],['Verify control lot','A. Lee','Fri'],['Close RCA','Team','Mon']].map((r,i)=>`<div><input type="checkbox" ${i===0?'checked':''} tabindex="-1"><span>${r[0]}</span><small>${r[1]}</small><em>${r[2]}</em></div>`).join('')}</div>`,'Table');
  if(n.includes('portfolio')) return shell(entry,`<div class="portfolio-grid">${['RCA-17','Yield+','Cycle','FDC'].map((x,i)=>`<div><b>${x}</b><span class="state ${i===2?'warn':'good'}">${i===2?'Watch':'On track'}</span></div>`).join('')}</div>`,'Table');
  if(n.includes('pivot')) return shell(entry,`<div class="pivot-live"><header><b>Group</b><b>Yield</b><b>Cycle</b></header><div><strong>Fab 1</strong><span>98.7</span><span>42.8</span></div><div><strong>Fab 2</strong><span>97.9</span><span>45.1</span></div><footer><b>Total</b><b>98.3</b><b>43.9</b></footer></div>`,'Table');
  if(n.includes('hierarchical')) return shell(entry,`<div class="tree-table"><div><b>▾ Fab 1</b><span>184</span></div><div class="child">▾ Etch<span>92</span></div><div class="leaf">Chamber A<span>48</span></div><div class="leaf">Chamber B<span>44</span></div><div class="child">▸ Dep<span>92</span></div></div>`,'Table');
  if(n.includes('evidence')) return shell(entry,`<div class="evidence-list"><div><i class="good"></i><span>Pressure excursion</span><b>Support</b></div><div><i class="warn"></i><span>Recipe unchanged</span><b>Contradict</b></div><div><i class="good"></i><span>Spatial match</span><b>Support</b></div></div>`,'Table');
  if(n.includes('clean') && !(entry.customTable?.rows||[]).some(r=>r?.some?.(v=>v!==null&&v!==undefined&&String(v).trim()!==''))) return shell(entry,`<div class="clean-empty-table"><header><i></i><i></i><i></i></header>${Array.from({length:3},()=>'<div><span></span><span></span><span></span></div>').join('')}<small>Add rows</small></div>`,'Table');
  if(n.includes('dense') && !(entry.customTable?.rows||[]).some(r=>r?.some?.(v=>v!==null&&v!==undefined&&String(v).trim()!==''))) return shell(entry,`<div class="dense-empty-table"><header>${Array.from({length:4},()=>'<i></i>').join('')}</header>${Array.from({length:7},()=>'<div>'+Array.from({length:4},()=>'<span></span>').join('')+'</div>').join('')}<small>Paste dense data</small></div>`,'Table');
  const c=entry.customTable;
  if(c?.headers?.length){
    const meaningful=(c.rows||[]).some(row=>Array.isArray(row)&&row.some(value=>value!==null&&value!==undefined&&String(value).trim()!==''));
    if(!meaningful) return shell(entry,`<div class="table-frame empty-data"><table><thead><tr>${c.headers.slice(0,4).map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead></table><div class="data-empty-state"><b>No rows yet</b><span>Paste data or open Data in the inspector.</span></div></div>`,'Table');
    return shell(entry,`<div class="table-frame"><table><thead><tr>${c.headers.slice(0,4).map((h,i)=>`<th data-direct="table-header:${i}" title="Double-click to rename">${esc(h)}</th>`).join('')}</tr></thead><tbody>${(c.rows||[]).slice(0,5).map((r,rowIndex)=>`<tr>${c.headers.slice(0,4).map((_,i)=>`<td data-direct="table-cell:${rowIndex}:${i}" title="Double-click to edit">${num(r[i],'')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`,'Table');
  }
  const rows=Array.isArray(entry.rows)?entry.rows:[];
  if(!rows.length) return shell(entry,`<div class="data-empty-state full"><b>No table data</b><span>Double-click to edit or paste a grid from your spreadsheet.</span></div>`,'Table');
  return shell(entry,`<div class="table-frame"><table><tbody>${rows.slice(0,5).map(row=>`<tr>${(Array.isArray(row)?row:Object.values(row||{})).slice(0,4).map(v=>`<td>${num(v,'')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`,'Table');
}

function matrix(entry){
  const n=entry.element.toLowerCase();
  if(entry.dataset_id&&Array.isArray(entry.matrix_long)&&entry.matrix_long.length){const rows=[...new Set(entry.matrix_long.map(cell=>String(cell.row??'')))].slice(0,6),columns=[...new Set(entry.matrix_long.map(cell=>String(cell.column??'')))].slice(0,6),values=entry.matrix_long.map(cell=>Number(cell.value)).filter(Number.isFinite),min=Math.min(...values),max=Math.max(...values),cell=(row,column)=>entry.matrix_long.find(item=>String(item.row??'')===row&&String(item.column??'')===column),heat=value=>Number.isFinite(Number(value))?Math.max(.08,Math.min(1,(Number(value)-min)/Math.max(1e-9,max-min))):0;return shell(entry,`<div class="matrix-bound" role="grid" aria-label="${esc(entry.title||entry.element)}"><div></div>${columns.map(column=>`<b>${esc(column)}</b>`).join('')}${rows.map(row=>`<b>${esc(row)}</b>${columns.map(column=>{const value=cell(row,column)?.value;return `<span role="gridcell" style="--heat:${heat(value)}" title="${esc(`${row} · ${column}: ${value??'Missing'}`)}">${num(value,'—')}</span>`;}).join('')}`).join('')}</div><div class="heat-legend"><i></i><span>${num(min)} → ${num(max)}</span></div>`,'Matrix');}
  if(entry.dataset_id&&Array.isArray(entry.matrix)&&entry.matrix.length) { const [headers,...rows]=entry.matrix; return shell(entry,`<div class="table-frame"><table><thead><tr>${headers.slice(0,4).map(value=>`<th>${esc(value)}</th>`).join('')}</tr></thead><tbody>${rows.slice(0,5).map(row=>`<tr>${row.slice(0,4).map(value=>`<td>${num(value,'')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`,'Matrix'); }
  if(n.includes('risk')) return shell(entry,`<div class="risk-matrix">${Array.from({length:16},(_,i)=>`<span class="r${Math.floor(i/4)+Math.floor(i%4)}"></span>`).join('')}<b style="--x:3;--y:2">●</b></div><div class="matrix-axes"><span>Likelihood →</span><span>Impact ↑</span></div>`,'Matrix');
  if(n.includes('raci')) return shell(entry,`<div class="raci-grid"><b></b><b>Eng</b><b>Ops</b><b>QA</b>${['Verify','Contain','Close'].flatMap((r,i)=>[`<strong>${r}</strong>`,`<span>${i?'C':'R'}</span>`,`<span>${i===1?'R':'A'}</span>`,`<span>I</span>`]).join('')}</div>`,'Matrix');
  if(n.includes('correlation')) return shell(entry,`<div class="correlation-live">${Array.from({length:25},(_,i)=>`<span class="${i%6===0?'diag':''}"></span>`).join('')}<i></i></div>`,'Matrix');
  if(n.includes('heatmap')) return shell(entry,`<div class="heat-grid heat-only">${Array.from({length:25},(_,i)=>`<span style="--heat:${((i*7)%10)/10}"></span>`).join('')}</div><div class="heat-legend"><i></i><span>Low → High</span></div>`,'Matrix');
  if(n.includes('weighted decision')) return shell(entry,`<div class="weighted-grid"><header><b>Option</b><b>0.5</b><b>0.3</b><b>0.2</b></header><div><strong>A</strong><span>5</span><span>3</span><span>4</span></div><div><strong>B</strong><span>4</span><span>5</span><span>2</span></div><footer><b>Weighted</b><em>4.2</em><em>3.9</em></footer></div>`,'Matrix');
  if(n.includes('decision')) return shell(entry,`<div class="decision-grid"><div></div><b>Impact</b><b>Risk</b><b>Total</b><strong>A</strong><span>5</span><span>2</span><em>8.4</em><strong>B</strong><span>3</span><span>1</span><em>7.1</em></div>`,'Matrix');
  if(n.includes('comparison')) return shell(entry,`<div class="comparison-matrix-live"><header><i></i><b>A</b><b>B</b><b>C</b></header>${['Speed','Risk','Cost'].map((x,i)=>`<div><strong>${x}</strong><span class="s${i}"></span><span class="s${i+1}"></span><span class="s${i+2}"></span></div>`).join('')}</div>`,'Matrix');
  if(n.includes('evidence matrix')) return shell(entry,`<div class="evidence-matrix-live"><header><b>Evidence</b><b>For</b><b>Against</b></header><div><span>Pressure</span><i>●</i><em></em></div><div><span>Recipe</span><i></i><em>●</em></div><div><span>Spatial</span><i>●</i><em></em></div></div>`,'Matrix');
  if(n.includes('contradiction matrix')) return shell(entry,`<div class="contradiction-matrix-live">${Array.from({length:9},(_,i)=>`<span class="${[2,4,6].includes(i)?'bad':''}">${[2,4,6].includes(i)?'!':''}</span>`).join('')}</div>`,'Matrix');
  if(n.includes('commonality')) return shell(entry,`<div class="commonality-live"><div><b>Shared</b><span>A</span><span>B</span></div><div><b>Unique</b><span>C</span></div><i></i></div>`,'Matrix');
  if(n.includes('doe design')) return shell(entry,`<div class="doe-matrix-live"><header><b>Run</b><b>A</b><b>B</b><b>AB</b></header>${Array.from({length:4},(_,i)=>`<div><strong>${i+1}</strong><span>${i%2?'+':'−'}</span><span>${i<2?'−':'+'}</span><span>${i===1||i===2?'+':'−'}</span></div>`).join('')}</div>`,'Matrix');
  if(n.includes('benchmark')) return shell(entry,`<div class="benchmark-matrix-live">${['Us','Peer A','Peer B'].map((x,i)=>`<div><b>${x}</b><i style="width:${82-i*13}%"></i><span>${92-i*7}</span></div>`).join('')}</div>`,'Matrix');
  return shell(entry,`<div class="matrix" role="grid">${Array.from({length:16},(_,i)=>`<div class="matrix-cell level-${(i*7)%5}">${i%5===0?'High':i%3===0?'Med':'Low'}</div>`).join('')}</div>`,'Matrix');
}

function timeline(entry){
  const n=entry.element.toLowerCase(), milestones=entry.milestones?.length?entry.milestones:[{label:'Discover',date:null},{label:'Validate',date:null},{label:'Implement',date:null},{label:'Verify',date:null}];
  if(entry.dataset_id){try{const dated=milestones.length&&milestones.every(item=>typeof item.date==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(item.date));const plan=prepareTimeline(dated?'dated':'sequence',{tasks:milestones.map((item,index)=>dated?{id:`task-${index}`,label:item.label,start:item.date,milestone:true}:{id:`task-${index}`,label:item.label,order:index}),dependencies:milestones.slice(1).map((_,index)=>({source:`task-${index}`,target:`task-${index+1}`}))});return shell(entry,`<div class="timeline-rail" data-timeline-plan="${esc(plan.fingerprint)}">${plan.tasks.slice(0,5).map((task,index)=>`<div class="tl-step"><span class="tl-dot"></span><div><b data-direct="milestone:${index}" title="Double-click to edit label">${esc(task.label)}</b><small>${esc(plan.mode==='dated'?task.start:`Step ${index+1}`)}</small></div></div>`).join('')}</div>`,'Timeline');}catch(error){return shell(entry,`<div class="data-empty-state full"><b>Timeline data needs review</b><span>${esc(error.message)}</span></div>`,'Timeline');}}
  if(n.includes('gantt')) return shell(entry,`<div class="gantt"><div class="gantt-labels"><span>Discover</span><span>Validate</span><span>Implement</span></div><div class="gantt-bars"><i style="--x:0;--w:34"></i><i style="--x:25;--w:42"></i><i style="--x:62;--w:34"></i></div></div>`,'Timeline');
  if(n.includes('swimlane')) return shell(entry,`<div class="swim-timeline"><div><b>Ops</b><i style="left:8%;width:32%"></i><i style="left:64%;width:22%"></i></div><div><b>Eng</b><i style="left:28%;width:40%"></i></div><div><b>QA</b><i style="left:58%;width:30%"></i></div></div>`,'Timeline');
  if(n.includes('calendar')) return shell(entry,`<div class="calendar-heat">${Array.from({length:35},(_,i)=>`<span class="h${(i*3)%5}"></span>`).join('')}</div>`,'Timeline');
  if(n.includes('schedule')) return shell(entry,`<div class="schedule-grid"><b>Mon</b><b>Tue</b><b>Wed</b><b>Thu</b><span></span><span class="task">Verify</span><span></span><span class="task alt">Close</span></div>`,'Timeline');
  if(n.includes('sequence')) return shell(entry,`<div class="sequence-strip">${milestones.slice(0,4).map((m,i)=>`<span><i>${i+1}</i><b data-direct="milestone:${i}" title="Double-click to edit label">${esc(m.label)}</b></span>`).join('<em>→</em>')}</div>`,'Timeline');
  if(n.includes('before/after')) return shell(entry,`<div class="before-after-time"><div><b>Before</b><i></i><span>188m</span></div><em>→</em><div><b>After</b><i class="short"></i><span>14m</span></div></div>`,'Timeline');
  if(n.includes('vertical')) return shell(entry,`<div class="timeline-vertical">${milestones.slice(0,4).map((m,i)=>`<div class="${i<2?'done':''}"><i></i><b>${esc(m.label)}</b><span>${esc(m.date||`Step ${i+1}`)}</span></div>`).join('')}</div>`,'Timeline');
  if(n.includes('event timeline')) return shell(entry,`<div class="event-timeline-live">${milestones.slice(0,4).map((m,i)=>`<div><span>${esc(m.date||`0${i+1}`)}</span><i></i><b>${esc(m.label)}</b></div>`).join('')}</div>`,'Timeline');
  if(n.includes('phase roadmap')) return shell(entry,`<div class="phase-roadmap-live">${milestones.slice(0,4).map((m,i)=>`<div class="p${i}"><b>Phase ${i+1}</b><span>${esc(m.label)}</span></div>`).join('')}</div>`,'Timeline');
  if(n.includes('dependency roadmap')) return shell(entry,`<div class="dependency-roadmap-live"><span>A</span><i>→</i><span>B</span><i class="down">↘</i><span>C</span><i>→</i><span>D</span></div>`,'Timeline');
  if(n.includes('milestone rail')) return shell(entry,`<div class="milestone-rail-live">${milestones.slice(0,4).map((m,i)=>`<span><i class="${i<2?'done':''}"></i><b>${esc(m.label)}</b></span>`).join('')}</div>`,'Timeline');
  return shell(entry,`<div class="timeline-rail">${milestones.slice(0,5).map((m,i)=>`<div class="tl-step ${i<2?'done':''}"><span class="tl-dot"></span><div><b>${esc(m.label)}</b><small>${esc(m.date||`Step ${i+1}`)}</small></div></div>`).join('')}</div>`,'Timeline');
}

function diagram(entry){
  const n=entry.element.toLowerCase();
  if(entry.dataset_id&&Array.isArray(entry.nodes)&&entry.nodes.length) { try{const graph=validateGraph('dag',{nodes:entry.nodes.map(node=>({id:String(node),label:String(node)})),edges:(Array.isArray(entry.edges)?entry.edges:[]).map(([source,target],index)=>({id:`edge-${index}`,source:String(source),target:String(target)}))});const nodes=graph.topologicalOrder.slice(0,4),edges=graph.edges.filter(edge=>nodes.includes(edge.source)&&nodes.includes(edge.target)),position=new Map(nodes.map((node,index)=>[node,{x:16+index*70,y:index%2?72:30}]));return shell(entry,`<svg class="diagram-svg flow-svg" data-graph-plan="${esc(graph.fingerprint)}" viewBox="0 0 300 140"><defs><marker id="bound-arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8Z"/></marker></defs>${edges.map(edge=>{const source=position.get(edge.source),target=position.get(edge.target);return `<path d="M${source.x+58} ${source.y+16} L${target.x} ${target.y+16}" marker-end="url(#bound-arr)"/>`;}).join('')}${nodes.map(node=>{const p=position.get(node);return `<rect x="${p.x}" y="${p.y}" width="58" height="32" rx="8"/><text x="${p.x+29}" y="${p.y+20}">${esc(node)}</text>`;}).join('')}</svg>`,'Diagram');}catch(error){return shell(entry,`<div class="data-empty-state full"><b>Diagram data needs review</b><span>${esc(error.message)}</span></div>`,'Diagram');} }
  if(n.includes('fishbone')) return shell(entry,`<svg class="diagram-svg fishbone-svg" viewBox="0 0 300 140"><path d="M36 70H266M248 58L266 70L248 82M70 70L48 36M112 70L92 30M154 70L135 38M82 70L58 105M130 70L108 113M181 70L158 108"/><text x="248" y="50">Effect</text><text x="25" y="31">Method</text><text x="71" y="25">Machine</text><text x="116" y="33">Material</text><text x="37" y="120">People</text><text x="90" y="132">Measure</text><text x="143" y="125">Environment</text></svg>`,'Diagram');
  if(n.includes('mind map')) return shell(entry,`<svg class="diagram-svg mindmap-svg" viewBox="0 0 300 140"><circle cx="150" cy="70" r="28"/><text x="150" y="74">RCA</text>${[[55,30,'Signal'],[55,110,'Control'],[245,30,'Cause'],[245,110,'Action']].map(([x,y,t])=>`<path d="M${x<150?122:178} 70Q150 ${y} ${x+(x<150?25:-25)} ${y}"/><rect x="${x-28}" y="${y-14}" width="56" height="28" rx="8"/><text x="${x}" y="${y+4}">${t}</text>`).join('')}</svg>`,'Diagram');
  if(n.includes('hierarchy')) return shell(entry,`<div class="hierarchy-tree"><div>Fab</div><section><div>Etch</div><div>Dep</div><div>Litho</div></section><footer><span>A</span><span>B</span><span>C</span><span>D</span></footer></div>`,'Diagram');
  if(n==='swimlane') return shell(entry,`<div class="swimlane-container-live"><div><b>Lane A</b><span></span></div><div><b>Lane B</b><span></span></div><div><b>Lane C</b><span></span></div></div>`,'Diagram');
  if(n.includes('swimlane process')) return shell(entry,`<div class="swim-process"><div class="lane"><b>Ops</b><span>Detect</span><span>Contain</span></div><div class="lane"><b>Eng</b><span>Analyze</span><span>Verify</span></div><div class="lane"><b>QA</b><span>Approve</span><span>Close</span></div></div>`,'Diagram');
  if(n.includes('sequence diagram')) return shell(entry,`<div class="sequence-diagram"><header><b>UI</b><b>Service</b><b>Store</b></header><div><i></i><span style="--y:1">request →</span><span style="--y:2">commit →</span><span style="--y:3">← ack</span></div></div>`,'Diagram');
  if(n.includes('decision tree')) return shell(entry,`<svg class="diagram-svg tree-svg" viewBox="0 0 300 140"><path d="M150 28V48M150 48L88 78M150 48L212 78M88 78L55 112M88 78L118 112M212 78L184 112M212 78L246 112"/><rect x="118" y="8" width="64" height="30" rx="8"/><text x="150" y="27">Decision</text>${[[58,67,'Yes'],[182,67,'No'],[25,105,'A'],[88,105,'B'],[155,105,'C'],[217,105,'D']].map(([x,y,t])=>`<rect x="${x}" y="${y}" width="58" height="26" rx="7"/><text x="${x+29}" y="${y+17}">${t}</text>`).join('')}</svg>`,'Diagram');
  if(n.includes('causal dag')) return shell(entry,`<svg class="diagram-svg dag-svg" viewBox="0 0 300 140"><path d="M55 70L120 35L190 60L250 30M120 35L190 60L245 110M55 70L140 108L190 60"/>${[[55,70,'A'],[120,35,'B'],[140,108,'C'],[190,60,'D'],[250,30,'E'],[245,110,'F']].map(([x,y,t])=>`<circle cx="${x}" cy="${y}" r="13"/><text x="${x}" y="${y+4}">${t}</text>`).join('')}</svg>`,'Diagram');
  if(n.includes('evidence graph')) return shell(entry,`<div class="evidence-graph-live"><b>Hypothesis</b><span class="support">+ Evidence A</span><span class="against">− Evidence B</span><span class="support">+ Evidence C</span></div>`,'Diagram');
  if(n.includes('dependency graph')) return shell(entry,`<div class="dependency-graph-live"><span>A</span><i>→</i><span>B</span><i>→</i><span>C</span><em>↘</em><span>D</span></div>`,'Diagram');
  if(n.includes('network graph')) return shell(entry,`<svg class="diagram-svg network-svg" viewBox="0 0 300 140"><path d="M65 70L130 34L195 60L245 28M65 70L135 110L195 60L242 112M130 34L135 110"/>${[[65,70,'A'],[130,34,'B'],[135,110,'C'],[195,60,'D'],[245,28,'E'],[242,112,'F']].map(([x,y,t],i)=>`<circle cx="${x}" cy="${y}" r="14" class="n${i}"/><text x="${x}" y="${y+4}">${t}</text>`).join('')}</svg>`,'Diagram');
  if(n.includes('container')||n.includes('subsystem')) return shell(entry,`<div class="container-subsystem-live"><section><b>Subsystem A</b><span>Service 1</span><span>Service 2</span></section><section><b>Subsystem B</b><span>Store</span></section></div>`,'Diagram');
  if(n.includes('architecture')) return shell(entry,`<div class="architecture-demo"><section><b>Application</b><span>UI</span><span>Service</span></section><section><b>Data</b><span>Reports</span><span>Preferences</span></section><i>semantic bridge</i></div>`,'Diagram');
  if(n.endsWith(' node')||['source node','process node','decision node','output node'].some(x=>n.includes(x))) return shell(entry,`<div class="single-node ${slug(entry.element)}"><i></i><b>${esc(entry.element.replace(' Node',''))}</b><span>Double-click to rename</span></div>`,'Diagram');
  if(n==='data flow') return shell(entry,`<div class="data-flow-live"><span>Source</span><i>⇢</i><b>Transform</b><i>⇢</i><span>Store</span></div>`,'Diagram');
  if(n==='flowchart') return shell(entry,`<div class="flowchart-live"><span>Start</span><i>↓</i><b>Decision?</b><div><em>Yes</em><em>No</em></div></div>`,'Diagram');
  if(n==='causal chain') return shell(entry,`<div class="causal-chain-live"><span>Signal</span><i>⇒</i><span>Mechanism</span><i>⇒</i><b>Effect</b></div>`,'Diagram');
  if(n==='transformation diagram') return shell(entry,`<div class="transform-diagram-live"><span>Input</span><div><i></i><i></i><i></i></div><b>Output</b></div>`,'Diagram');
  if(n==='pipeline diagram') return shell(entry,`<div class="pipeline-live"><span>Ingest</span><i></i><span>Process</span><i></i><span>Validate</span><i></i><b>Publish</b></div>`,'Diagram');
  if(n==='value stream') return shell(entry,`<div class="value-stream-live"><span><b>VA</b><small>12m</small></span><i>→</i><span class="wait"><b>Wait</b><small>38m</small></span><i>→</i><span><b>VA</b><small>8m</small></span></div>`,'Diagram');
  if(n==='process flow') return shell(entry,`<div class="process-flow-live"><span>Source</span><i>→</i><b>Process</b><i>→</i><span>Outcome</span></div>`,'Diagram');
  const nodes=(entry.nodes||['Source','Process','Outcome']).slice(0,4); return shell(entry,`<svg class="diagram-svg flow-svg" viewBox="0 0 300 140"><defs><marker id="r13arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8Z"/></marker></defs>${nodes.map((x,i)=>`<rect x="${16+i*70}" y="${i%2?72:30}" width="58" height="32" rx="8"/><text x="${45+i*70}" y="${i%2?92:50}">${esc(x)}</text>`).join('')}${nodes.slice(0,-1).map((_,i)=>`<path d="M${74+i*70} ${i%2?88:46} C${90+i*70} ${i%2?88:46},${92+i*70} ${(i+1)%2?88:46},${86+(i+1)*70} ${(i+1)%2?88:46}" marker-end="url(#r13arr)"/>`).join('')}</svg>`,'Diagram');
}

function image(entry){
  const n=entry.element.toLowerCase(),src=entry.src?`background-image:url('${String(entry.src).replace(/'/g,'%27')}');background-size:${entry.fit==='fit'?'contain':'cover'};background-position:${esc(entry.focal||'50% 50%')};background-repeat:no-repeat;`:'';
  if(n.includes('before/after')) return shell(entry,`<div class="image-pair"><div style="${src}"><span>Before</span></div><div style="${src}"><span>After</span></div></div>`,'Media');
  if(n.includes('gallery')) return shell(entry,`<div class="image-gallery">${[1,2,3,4].map(i=>`<div style="${src}"><span>${i}</span></div>`).join('')}</div>`,'Media');
  if(n.includes('annotated')) return shell(entry,`<div class="image-stage" style="${src}"><i style="left:64%;top:34%"></i><b style="left:48%;top:54%">Critical region</b></div>`,'Media');
  if(n.includes('zoom')||n.includes('detail inset')) return shell(entry,`<div class="image-stage" style="${src}"><i class="focus-box"></i><div class="detail-inset" style="${src}"></div></div>`,'Media');
  if(n.includes('slider')) return shell(entry,`<div class="image-slider"><div style="${src}"></div><div style="${src}"></div><i></i></div>`,'Media');
  if(n==='screenshot frame') return shell(entry,`<div class="screenshot-frame-live"><header><i></i><i></i><i></i><span>Application</span></header><div style="${src}"><b>${entry.src?'':'Drop screenshot'}</b></div></div>`,'Media');
  if(n.includes('image + caption')) return shell(entry,`<figure class="captioned-image-live"><div style="${src}">${entry.src?'':'Image'}</div><figcaption>${esc(entry.caption||'Add a concise caption')}</figcaption></figure>`,'Media');
  if(n.includes('svg / illustration')) return shell(entry,`<div class="illustration-live"><svg viewBox="0 0 200 110"><circle cx="55" cy="55" r="25"/><rect x="108" y="31" width="48" height="48" rx="9"/><path d="M80 55H108"/></svg><span>Vector illustration</span></div>`,'Media');
  return shell(entry,`<div class="image-stage ${n.includes('hero')?'hero-media':''}" style="${src}">${entry.src?'':`<span>Paste or upload image</span>`}</div>${entry.caption?`<p class="image-caption">${esc(entry.caption)}</p>`:''}`,'Media');
}

function composite(entry){
  const n=entry.element.toLowerCase(),kind=entry.engine,statement=esc(entry.statement||entry.element),detail=esc(entry.detail||'Add decision-relevant context.');
  if(kind==='EvidenceCompositeEngine'){
    if(n.includes('leading hypothesis')) return shell(entry,`<div class="hypothesis-live"><span>Leading hypothesis</span><strong>${statement}</strong><div><i style="width:78%"></i><b>Confidence</b></div></div>`,'Evidence');
    if(n==='evidence card') return shell(entry,`<div class="evidence-card-live"><header><i class="good"></i><b>${statement}</b></header><p>${detail}</p><footer><span>Source</span><em>Supports</em></footer></div>`,'Evidence');
    if(n.includes('evidence stack')) return shell(entry,`<div class="evidence-stack-live"><div><i></i><span>Observation A</span></div><div><i></i><span>Observation B</span></div><div><i class="warn"></i><span>Observation C</span></div></div>`,'Evidence');
    if(n.includes('polarity')) return shell(entry,`<div class="polarity-live"><div class="good"><b>Supports</b><span>3</span></div><div class="bad"><b>Contradicts</b><span>1</span></div><footer><i></i><i></i><i></i><em></em></footer></div>`,'Evidence');
    if(n.includes('causal chain component')) return shell(entry,`<div class="evidence-causal-live"><span>Signal</span><i>→</i><span>Mechanism</span><i>→</i><b>Effect</b></div>`,'Evidence');
    if(n.includes('root cause status')) return shell(entry,`<div class="root-status-live"><header><b>Root cause</b><span>Validated</span></header><div><i class="done"></i><i class="done"></i><i class="done"></i><i></i></div><small>Evidence → test → verify → close</small></div>`,'Evidence');
    if(n.includes('containment')) return shell(entry,`<div class="containment-live"><i>◈</i><div><b>Containment active</b><span>Quarantine affected lots</span><span>Hold chamber release</span></div></div>`,'Evidence');
    if(n.includes('corrective action')) return shell(entry,`<div class="corrective-live"><header><b>Corrective action</b><span>Open</span></header><p>${detail}</p><footer><i>Owner</i><em>Due Fri</em><b>□</b></footer></div>`,'Evidence');
    if(n.includes('verification')) return shell(entry,`<div class="verification-live"><b>Verification</b><label><i>✓</i> Control lot</label><label><i>✓</i> Spatial response</label><label><i></i> Sustained window</label></div>`,'Evidence');
    if(n.includes('next discriminating')) return shell(entry,`<div class="next-test-live"><span>Next test</span><b>Run the fastest falsifiable experiment</b><div><i>1</i><em>Control</em><i>2</i><em>Affected</em><i>3</i><em>Compare</em></div></div>`,'Evidence');
    if(n.includes('open questions')) return shell(entry,`<div class="open-questions-live"><b>Open questions</b><ul><li>What would falsify this?</li><li>Which control discriminates?</li><li>What remains unexplained?</li></ul></div>`,'Evidence');
  }
  if(kind==='DecisionCompositeEngine'){
    if(n.includes('recommendation hero')) return shell(entry,`<div class="recommendation-live"><span>Recommendation</span><strong>${statement}</strong><p>${detail}</p><button tabindex="-1">Approve path</button></div>`,'Decision');
    if(n.includes('option card')) return shell(entry,`<div class="option-live"><header><b>Option A</b><span>Preferred</span></header><p>${detail}</p><footer><i>Impact 5</i><i>Risk 2</i><i>Cost 3</i></footer></div>`,'Decision');
    if(n.includes('tradeoff')) return shell(entry,`<div class="tradeoff-live"><div><b>Impact</b><i style="width:82%"></i></div><div><b>Cost</b><i style="width:46%"></i></div><div><b>Risk</b><i style="width:31%"></i></div></div>`,'Decision');
    if(n.includes('risk callout')) return shell(entry,`<div class="risk-callout-live"><i>!</i><div><b>Decision risk</b><p>${detail}</p></div><span>Medium</span></div>`,'Decision');
    if(n.includes('decision needed')) return shell(entry,`<div class="decision-needed-live"><span>Decision needed</span><strong>${statement}</strong><footer><button tabindex="-1">Choose A</button><button tabindex="-1">Choose B</button></footer></div>`,'Decision');
    if(n.includes('reversibility')) return shell(entry,`<div class="reversibility-live"><div><i></i><b>Reversible</b></div><span>Low switching cost</span><em>↶</em></div>`,'Decision');
    if(n.includes('constraint')) return shell(entry,`<div class="constraint-live"><b>Constraints</b><span>Budget ≤ $250k</span><span>Window ≤ 14 days</span><span>No recipe change</span></div>`,'Decision');
    if(n.includes('consequence')) return shell(entry,`<div class="consequence-live"><span>Decision</span><i>→</i><div><b>Immediate</b><em>Containment</em></div><i>→</i><div><b>Downstream</b><em>Capacity</em></div></div>`,'Decision');
  }
  if(kind==='ProjectCompositeEngine'){
    if(n==='project card') return shell(entry,`<div class="project-card-live"><header><b>${statement}</b><span>On track</span></header><div><i style="width:68%"></i></div><footer><span>Owner</span><em>68%</em></footer></div>`,'Project');
    if(n.includes('portfolio tile')) return shell(entry,`<div class="portfolio-tiles-live"><span>RCA-17<i class="good"></i></span><span>Yield+<i class="good"></i></span><span>Cycle<i class="warn"></i></span><span>FDC<i class="good"></i></span></div>`,'Project');
    if(n.includes('milestone status')) return shell(entry,`<div class="milestone-status-live"><div><i class="done"></i><b>Scope</b></div><div><i class="done"></i><b>Verify</b></div><div><i></i><b>Close</b></div></div>`,'Project');
    if(n.includes('workstream summary')) return shell(entry,`<div class="workstream-live"><b>Workstreams</b><span><i class="good"></i>Containment<em>Done</em></span><span><i class="warn"></i>Validation<em>Active</em></span><span><i></i>Closure<em>Next</em></span></div>`,'Project');
    if(n.includes('accomplishment')) return shell(entry,`<div class="accomplishment-live"><b>Completed</b><label><i>✓</i> Isolated chamber</label><label><i>✓</i> Reproduced signature</label><label><i>✓</i> Verified control</label></div>`,'Project');
    if(n.includes('next actions')) return shell(entry,`<div class="next-actions-live"><b>Next actions</b><div><span>01</span><em>Run split lot</em></div><div><span>02</span><em>Validate window</em></div><div><span>03</span><em>Close RCA</em></div></div>`,'Project');
    if(n.includes('change since')) return shell(entry,`<div class="change-live"><header><b>Since last review</b><span>3 changes</span></header><p><i>+</i> Confidence increased</p><p><i>+</i> Control lot passed</p><p><em>~</em> Due date moved</p></div>`,'Project');
    if(n.includes('owner / contributor')) return shell(entry,`<div class="owners-live"><b>Owner</b><i>JK</i><span>J. Kim</span><hr><b>Contributors</b><div><i>AL</i><i>MS</i><i>RY</i></div></div>`,'Project');
  }
  if(n.includes('contradiction')) return shell(entry,`<div class="contradiction-card"><i>!</i><div><b>${esc(entry.statement||'Contradiction detected')}</b><p>${esc(entry.detail||'One high-confidence observation conflicts with the leading explanation.')}</p></div></div>`,'Evidence');
  if(n.includes('open questions')||n.includes('next discriminating')) return shell(entry,`<ol class="question-list"><li>What observation would falsify the current hypothesis?</li><li>Which control population best discriminates the cause?</li><li>What is the fastest reversible test?</li></ol>`,'Evidence');
  if(n.includes('pros / cons')) return shell(entry,`<div class="pros-cons"><div><b>Pros</b><span>High impact</span><span>Reversible</span></div><div><b>Cons</b><span>Validation cost</span><span>Dependency</span></div></div>`,'Decision');
  if(n.includes('risk register')) return shell(entry,`<div class="risk-register"><div><b>Supply</b><span>Med</span></div><div><b>Quality</b><span>Low</span></div><div><b>Schedule</b><span>High</span></div></div>`,'Decision');
  if(n.includes('quadrant')) return shell(entry,`<div class="quadrant"><i>Quick wins</i><i>Strategic</i><i>Fill-ins</i><i>Avoid</i><b style="left:64%;top:30%"></b><b style="left:34%;top:58%"></b></div>`,'Project');
  if(n.includes('health strip')) return shell(entry,`<div class="health-strip"><span><i class="good"></i>Scope</span><span><i class="good"></i>Cost</span><span><i class="warn"></i>Schedule</span><span><i class="good"></i>Quality</span></div>`,'Project');
  const eyebrow=kind==='EvidenceCompositeEngine'?'Evidence':kind==='DecisionCompositeEngine'?'Decision':'Project';
  return shell(entry,`<div class="composite-hero"><span class="eyebrow">${eyebrow}</span><strong>${esc(entry.statement||entry.element)}</strong><p>${esc(entry.detail||'Add the decision-relevant evidence, context, and next action.')}</p></div><div class="chip-row"><span class="state good">${esc(entry.status||'Open')}</span><span class="chip">Owner · unassigned</span></div>`,eyebrow);
}

function wafer(entry){
  const n=entry.element.toLowerCase();
  const fabRows=Array.isArray(entry.fab_rows)?entry.fab_rows:[],fabFields=Array.isArray(entry.fab_fields)?entry.fab_fields:[],fabMapping=entry.fab_mapping||{},fieldName=role=>fabFields.find(field=>field.id===fabMapping[role])?.name||null;
  if(entry.dataset_id&&fabRows.length&&(n.includes('matrix')||n.includes('heatmap'))){const rowField=fieldName('tool')||fieldName('product')||fieldName('category'),columnField=fieldName('chamber')||fieldName('recipe')||fieldName('series'),valueField=fieldName('value');if(rowField&&columnField&&valueField){const rows=[...new Set(fabRows.map(row=>String(row[rowField]??'')))].filter(Boolean).slice(0,5),columns=[...new Set(fabRows.map(row=>String(row[columnField]??'')))].filter(Boolean).slice(0,5),cells=fabRows.filter(row=>Number.isFinite(Number(row[valueField]))),values=cells.map(row=>Number(row[valueField])),min=Math.min(...values),max=Math.max(...values),valueAt=(row,column)=>cells.find(cell=>String(cell[rowField])===row&&String(cell[columnField])===column)?.[valueField],heat=value=>Number.isFinite(Number(value))?Math.max(.08,Math.min(1,(Number(value)-min)/Math.max(1e-9,max-min))):0;return shell(entry,`<div class="matrix-bound" role="grid" aria-label="${esc(entry.title||entry.element)}"><div></div>${columns.map(column=>`<b>${esc(column)}</b>`).join('')}${rows.map(row=>`<b>${esc(row)}</b>${columns.map(column=>{const value=valueAt(row,column);return `<span style="--heat:${heat(value)}">${num(value,'—')}</span>`;}).join('')}`).join('')}</div><div class="heat-legend"><i></i><span>${esc(rowField)} × ${esc(columnField)}</span></div>`,'Fab');}}
  if(entry.dataset_id&&fabRows.length&&n.includes('route diagram')){const routeField=fieldName('process')||fieldName('category')||fieldName('time'),steps=[...new Set(routeField?fabRows.map(row=>String(row[routeField]??'')).filter(Boolean):[])].slice(0,5);if(steps.length)return shell(entry,`<div class="route-flow">${steps.map((step,index)=>`${index?'<i>→</i>':''}<span>${esc(step)}</span>`).join('')}</div>`,'Fab');}
  if(entry.dataset_id&&Array.isArray(entry.observations)&&entry.observations.length) { const observed=new Map(entry.observations.map(row=>[`${row.x}:${row.y}`,row.value])); const values=entry.observations.map(row=>Number(row.value)).filter(Number.isFinite);const min=Math.min(...values),max=Math.max(...values),level=value=>Number.isFinite(Number(value))?Math.max(0,Math.min(4,Math.round((Number(value)-min)/Math.max(1,max-min)*4))):0;const cells=[];for(let y=-4;y<=4;y+=1)for(let x=-5;x<=5;x+=1)if(x*x+y*y<28){const value=observed.get(`${x}:${y}`);cells.push(`<span class="die heat-${level(value)}" style="--x:${x+5};--y:${y+4}" title="${esc(value??'Missing')}"></span>`);}const identity=[['Wafer',entry.wafer_id],['Lot',entry.lot],['Tool',entry.tool],['Chamber',entry.chamber],['Recipe',entry.recipe],['Step',entry.process]].filter(([,value])=>value!==null&&value!==undefined&&String(value).trim()!=='').slice(0,3);return shell(entry,`<div class="wafer-demo"><div class="wafer-grid">${cells.join('')}</div><span class="wafer-notch"></span></div>${identity.length?`<div class="metric-meta">${identity.map(([label,value])=>`<span>${esc(label)} · ${esc(value)}</span>`).join('')}</div>`:''}`,'Fab'); }
  if(n.includes('route commonality matrix')) return shell(entry,`<div class="route-commonality-live"><header><b>Step</b><b>A</b><b>B</b><b>C</b></header>${['Litho','Etch','Dep','CMP'].map((x,i)=>`<div><strong>${x}</strong><i class="${i===1?'hot':''}"></i><i></i><i class="${i===2?'hot':''}"></i></div>`).join('')}</div>`,'Fab');
  if(n.includes('product × chamber')) return shell(entry,`<div class="product-chamber-live"><header><b></b><b>C1</b><b>C2</b><b>C3</b></header>${['P1','P2','P3','P4'].map((x,i)=>`<div><strong>${x}</strong><span class="h${i}"></span><span class="h${i+1}"></span><span class="h${i+2}"></span></div>`).join('')}</div>`,'Fab');
  if(n.includes('tool × recipe heatmap')) return shell(entry,`<div class="recipe-heat-live">${Array.from({length:20},(_,i)=>`<span class="h${(i*3)%5}"></span>`).join('')}<i></i></div><div class="heat-legend"><i></i><span>Recipe sensitivity</span></div>`,'Fab');
  if(n.includes('matrix')||n.includes('heatmap')) return shell(entry,`<div class="tool-matrix"><b></b><b>C1</b><b>C2</b><b>C3</b>${['T1','T2','T3'].flatMap((t,r)=>[`<strong>${t}</strong>`,...Array.from({length:3},(_,c)=>`<span class="h${(r*3+c*2)%5}">${(82+r*4+c*3)}%</span>`)]).join('')}</div>`,'Fab');
  if(n.includes('golden vs affected profile')) return shell(entry,`<div class="golden-profile-live"><svg viewBox="0 0 260 105"><path class="golden" d="M15 78L55 70L95 63L135 57L175 49L215 43L250 38"/><path class="affected" d="M15 82L55 74L95 45L135 53L175 29L215 24L250 18"/></svg><div><span><i></i>Golden</span><span><i></i>Affected</span></div></div>`,'Fab');
  if(n.includes('lot trajectory')) return shell(entry,`<svg class="profile-svg lot-trajectory-live" viewBox="0 0 260 120"><path d="M15 94H250M15 70H250M15 46H250M15 22H250" class="gridline"/><path d="M18 82L58 75L98 48L138 53L178 31L218 24L248 20" class="accent-line"/>${[[18,82],[58,75],[98,48],[138,53],[178,31],[218,24],[248,20]].map(([x,y])=>`<circle cx="${x}" cy="${y}" r="3"/>`).join('')}</svg>`,'Fab');
  if(n.includes('trajectory')||n.includes('profile')) return shell(entry,`<svg class="profile-svg" viewBox="0 0 260 120"><path d="M15 94H250M15 70H250M15 46H250M15 22H250" class="gridline"/><path d="M18 82L58 75L98 48L138 53L178 31L218 24L248 20" class="accent-line"/><path d="M18 87L58 84L98 76L138 70L178 62L218 59L248 55" class="comparison-line"/></svg><div class="metric-meta"><span>Affected</span><span>Golden</span></div>`,'Fab');
  if(n.includes('distribution')) return shell(entry,`<svg class="distribution-svg" viewBox="0 0 260 120"><path d="M15 98H248"/><path d="M20 97C55 97 60 25 103 25C145 25 146 97 178 97" class="comparison-line"/><path d="M78 97C110 97 119 45 155 45C197 45 198 97 240 97" class="accent-line"/></svg>`,'Fab');
  if(n.includes('alarm timeline')) return shell(entry,`<div class="alarm-time"><i style="left:12%"></i><i style="left:42%"></i><i class="bad" style="left:66%"></i><i style="left:84%"></i><span></span></div>`,'Fab');
  if(n.includes('route diagram')) return shell(entry,`<div class="route-flow"><span>Litho</span><i>→</i><span>Etch</span><i>→</i><span>Dep</span><i>→</i><span>Metrology</span></div>`,'Fab');
  const cells=[];for(let y=-4;y<=4;y++)for(let x=-5;x<=5;x++)if(x*x+y*y<28){const h=(x*3+y*5+30)%5;cells.push(`<span class="die heat-${h}" style="--x:${x+5};--y:${y+4}"></span>`);}
  if(n.includes('difference map')) return shell(entry,`<div class="wafer-demo difference-wafer"><div class="wafer-grid">${cells.join('')}</div><i>−</i><b>+</b><span class="wafer-notch"></span></div>`,'Fab');
  if(n.includes('overlay')) return shell(entry,`<div class="wafer-demo overlay-wafer"><div class="wafer-grid">${cells.join('')}</div><div class="overlay-ring"></div><span class="wafer-notch"></span></div>`,'Fab');
  if(n.includes('spatial cluster')) return shell(entry,`<div class="wafer-demo cluster-wafer"><div class="wafer-grid">${cells.join('')}</div><i class="cluster c1"></i><i class="cluster c2"></i><i class="cluster c3"></i><span class="wafer-notch"></span></div>`,'Fab');
  return shell(entry,`<div class="wafer-demo"><div class="wafer-grid">${cells.join('')}</div><span class="wafer-notch"></span></div>`,'Fab');
}

function smartLayout(entry){
  const n=entry.element.toLowerCase(),count=n.includes('masonry')?6:4;
  if(n.includes('divider')) return shell(entry,`<div class="divider-demo"><span>Section A</span><i></i><span>Section B</span></div>`,'Layout');
  if(n.includes('spacer')) return shell(entry,`<div class="spacer-demo"><span>14</span><i></i><span>24</span><i></i><span>32</span></div>`,'Layout');
  if(n.includes('tabs')) return shell(entry,`<div class="demo-tabs"><button class="active">Overview</button><button>Evidence</button><button>Risks</button></div><div class="tab-preview"></div>`,'Layout');
  if(n.includes('accordion')) return shell(entry,`<div class="accordion-demo"><div>Summary <b>−</b></div><p>Expanded detail remains within the governed region.</p><div>Evidence <b>+</b></div><div>Notes <b>+</b></div></div>`,'Layout');
  return shell(entry,`<div class="layout-demo ${slug(entry.element)}">${Array.from({length:count},(_,i)=>`<span class="layout-block b${i+1}"></span>`).join('')}</div>`,'Layout');
}

function text(entry){
  const n=entry.element.toLowerCase(),body=esc(entry.text||entry.body||'Write report narrative here.');
  if(n.includes('hero title')) return shell(entry,`<div class="hero-copy">${body}</div>`,'Text');
  if(n.includes('section heading')) return shell(entry,`<div class="section-heading-render"><span>02</span><b>${body}</b></div>`,'Text');
  if(n.includes('eyebrow')||n.includes('kicker')) return shell(entry,`<div class="eyebrow-render">${body}</div>`,'Text');
  if(n.includes('executive statement')) return shell(entry,`<blockquote class="statement-render">${body}</blockquote>`,'Text');
  if(n.includes('key takeaway')) return shell(entry,`<div class="takeaway-render"><i>✓</i><strong>${body}</strong></div>`,'Text');
  if(n.includes('numbered')) return shell(entry,`<div class="numbered-insight"><b>01</b><p>${body}</p></div>`,'Text');
  if(n.includes('quote')) return shell(entry,`<blockquote class="quote-render">“${body}”</blockquote><span class="quote-source">Review synthesis</span>`,'Text');
  if(n.includes('annotation')) return shell(entry,`<div class="annotation-render"><i></i><span>${body}</span></div>`,'Text');
  if(n.includes('footnote')||n.includes('source')) return shell(entry,`<div class="source-render"><b>Source</b><span>${body}</span></div>`,'Text');
  if(n.includes('definition')) return shell(entry,`<dl class="definition-render"><dt>${esc(entry.title)}</dt><dd>${body}</dd></dl>`,'Text');
  if(n.includes('callout')) return shell(entry,`<div class="callout-render"><i>!</i><p>${body}</p></div>`,'Text');
  if(n.includes('code')) return shell(entry,`<pre class="code-render"><code>${body}</code></pre>`,'Text');
  if(n.includes('sequence')) return shell(entry,`<ol class="sequence-render">${body.split(/\n|\.\s+/).filter(Boolean).slice(0,4).map(x=>`<li>${esc(x)}</li>`).join('')}</ol>`,'Text');
  if(n.includes('metadata')) return shell(entry,`<div class="metadata-render"><span>${body}</span><b>Updated now</b></div>`,'Text');
  return shell(entry,`<p class="body-copy narrative-render">${body}</p>`,'Text');
}

function chartRows(entry){
  const raw=Array.isArray(entry.data)&&entry.data.length?entry.data:Array.isArray(entry.rows)?entry.rows:[];
  return raw.map((r,i)=>Array.isArray(r)?{label:String(r[0]??`Row ${i+1}`),value:r[1],extra:r.slice(2)}:{label:String(r?.label??`Row ${i+1}`),value:r?.value,extra:[]});
}
function chartEmpty(entry,n,W,H,left,right,top,plotW,plotH){
  const note='<small class="empty-hint">Add data</small>';
  if(n==='vertical bar') return shell(entry,`<div class="empty-bars vertical">${Array.from({length:4},(_,i)=>`<i style="height:${32+i*13}%"></i>`).join('')}</div>${note}`,'Chart');
  if(n==='horizontal bar') return shell(entry,`<div class="empty-hbars">${Array.from({length:3},(_,i)=>`<span><i style="width:${48+i*14}%"></i></span>`).join('')}</div>${note}`,'Chart');
  if(n==='grouped bar') return shell(entry,`<div class="empty-grouped">${Array.from({length:3},()=>'<span><i></i><b></b></span>').join('')}</div>${note}`,'Chart');
  if(n==='stacked bar') return shell(entry,`<div class="empty-stacked">${Array.from({length:4},()=>'<span><i></i><b></b></span>').join('')}</div>${note}`,'Chart');
  if(n.includes('100% stacked')) return shell(entry,`<div class="empty-stacked percent">${Array.from({length:4},()=>'<span><i></i><b></b><em></em></span>').join('')}</div>${note}`,'Chart');
  if(n.includes('paired before')) return shell(entry,`<div class="empty-paired">${Array.from({length:3},()=>'<span><i></i><b></b></span>').join('')}</div><div class="empty-legend"><i></i>Before <b></b>After</div>${note}`,'Chart');
  if(n.includes('dumbbell')) return shell(entry,`<div class="empty-dumbbell">${Array.from({length:3},(_,i)=>`<span><i style="left:${18+i*4}%"></i><b style="left:${68+i*5}%"></b></span>`).join('')}</div>${note}`,'Chart');
  if(n.includes('slope')) return shell(entry,`<svg class="viz-svg empty-slope" viewBox="0 0 ${W} ${H}"><path d="M34 92L226 32"/><path d="M34 52L226 70"/><path d="M34 78L226 58"/></svg>${note}`,'Chart');
  if(n.includes('waterfall')) return shell(entry,`<div class="empty-waterfall"><i></i><span></span><span></span><b></b><em></em></div>${note}`,'Chart');
  if(n==='line chart') return shell(entry,`<svg class="viz-svg empty-line" viewBox="0 0 ${W} ${H}"><path d="M${left} ${top+plotH*.78} L70 70 L120 76 L170 38 L${W-right} 28"/></svg>${note}`,'Chart');
  if(n==='multi-line') return shell(entry,`<svg class="viz-svg empty-multiline" viewBox="0 0 ${W} ${H}"><path d="M22 86L75 58L126 70L180 32L250 48"/><path d="M22 55L75 72L126 42L180 61L250 25"/></svg>${note}`,'Chart');
  if(n==='area chart') return shell(entry,`<svg class="viz-svg empty-area" viewBox="0 0 ${W} ${H}"><path d="M22 96L22 78L75 62L126 70L180 38L250 30L250 96Z"/></svg>${note}`,'Chart');
  if(n==='stacked area') return shell(entry,`<svg class="viz-svg empty-stacked-area" viewBox="0 0 ${W} ${H}"><path d="M22 96L22 72L75 62L126 67L180 48L250 43L250 96Z"/><path d="M22 72L22 52L75 44L126 49L180 27L250 21L250 43L180 48L126 67L75 62Z"/></svg>${note}`,'Chart');
  if(n==='sparkline') return shell(entry,`<div class="empty-spark"><svg viewBox="0 0 220 70"><path d="M5 58L45 44L83 49L122 25L164 34L215 12"/></svg></div>${note}`,'Chart');
  if(n==='step chart') return shell(entry,`<svg class="viz-svg empty-step" viewBox="0 0 ${W} ${H}"><path d="M22 88H70V68H116V72H166V42H210V25H250"/></svg>${note}`,'Chart');
  if(n==='scatter plot') return shell(entry,`<svg class="viz-svg empty-scatter" viewBox="0 0 ${W} ${H}">${[[38,83],[70,60],[99,72],[137,44],[181,52],[226,25]].map(([x,y])=>`<circle cx="${x}" cy="${y}" r="4"/>`).join('')}</svg>${note}`,'Chart');
  if(n==='regression scatter') return shell(entry,`<svg class="viz-svg empty-regression" viewBox="0 0 ${W} ${H}"><path d="M28 94L238 22"/>${[[43,78],[76,71],[104,54],[142,57],[181,38],[220,31]].map(([x,y])=>`<circle cx="${x}" cy="${y}" r="3.5"/>`).join('')}</svg>${note}`,'Chart');
  if(n==='bubble plot') return shell(entry,`<svg class="viz-svg empty-bubbles" viewBox="0 0 ${W} ${H}">${[[48,78,7],[83,54,12],[122,72,5],[166,42,16],[216,34,9]].map(([x,y,r])=>`<circle cx="${x}" cy="${y}" r="${r}"/>`).join('')}</svg>${note}`,'Chart');
  if(n.includes('histogram')) return shell(entry,`<div class="empty-hist">${[18,34,58,82,70,42,22].map(h=>`<i style="height:${h}%"></i>`).join('')}</div>${note}`,'Chart');
  if(n.includes('box plot')) return shell(entry,`<div class="empty-boxplot"><span></span><i></i><b></b><em></em></div>${note}`,'Chart');
  if(n.includes('violin')) return shell(entry,`<svg class="viz-svg empty-violin" viewBox="0 0 ${W} ${H}"><path d="M130 10C94 28 101 48 114 59C96 76 100 98 130 111C160 98 164 76 146 59C159 48 166 28 130 10Z"/><line x1="130" y1="12" x2="130" y2="108"/></svg>${note}`,'Chart');
  if(n.includes('strip')||n.includes('dot')) return shell(entry,`<svg class="viz-svg empty-strip" viewBox="0 0 ${W} ${H}">${Array.from({length:12},(_,i)=>`<circle cx="${30+(i%6)*38}" cy="${48+(i%3)*12}" r="3.5"/>`).join('')}</svg>${note}`,'Chart');
  if(n==='ecdf') return shell(entry,`<svg class="viz-svg empty-ecdf" viewBox="0 0 ${W} ${H}"><path d="M22 98H52V86H86V70H118V57H158V41H202V27H248V15"/></svg>${note}`,'Chart');
  if(n==='pareto') return shell(entry,`<div class="empty-pareto">${[86,67,48,32,20].map(h=>`<i style="height:${h}%"></i>`).join('')}<svg viewBox="0 0 240 100"><path d="M18 78L66 53L112 37L160 28L214 22"/></svg></div>${note}`,'Chart');
  if(n==='treemap') return shell(entry,`<div class="empty-treemap"><span></span><i></i><b></b><em></em></div>${note}`,'Chart');
  if(n==='donut') return shell(entry,`<div class="empty-donut donut"><i></i></div>${note}`,'Chart');
  if(n==='pie') return shell(entry,`<div class="empty-donut pie"><i></i></div>${note}`,'Chart');
  if(n==='funnel') return shell(entry,`<div class="empty-funnel"><i></i><i></i><i></i><i></i></div>${note}`,'Chart');
  if(n==='sankey') return shell(entry,`<svg class="viz-svg empty-sankey" viewBox="0 0 ${W} ${H}"><rect x="20" y="20" width="10" height="76"/><rect x="230" y="18" width="10" height="38"/><rect x="230" y="70" width="10" height="30"/><path d="M30 38C105 38 150 28 230 30"/><path d="M30 72C105 72 150 84 230 84"/></svg>${note}`,'Chart');
  return shell(entry,`<div class="chart-empty-state"><svg class="viz-svg" viewBox="0 0 ${W} ${H}"><path class="gridline" d="M${left} ${top+plotH}H${W-right}"/></svg><div><b>No chart data</b><span>Double-click to edit.</span></div></div>`,'Chart');
}

function chart(entry){
  const rows=chartRows(entry), n=entry.element.toLowerCase(), W=260,H=120,left=22,right=10,top=10,bottom=22,plotW=W-left-right,plotH=H-top-bottom;
  const valid=rows.map((r,i)=>({...r,i,v:typeof r.value==='number'&&Number.isFinite(r.value)?r.value:null}));
  const nums=valid.map(r=>r.v).filter(v=>v!==null), max=Math.max(1,...nums.map(Math.abs)), min=Math.min(0,...nums);
  if(!nums.length) return chartEmpty(entry,n,W,H,left,right,top,plotW,plotH);
  if(n.includes('pie')||n.includes('donut')){
    const total=nums.reduce((a,b)=>a+Math.max(0,b),0)||1, first=Math.max(0,valid[0]?.v||0)/total*100;
    return shell(entry,`<div class="chart-donut-wrap"><svg class="viz-svg" viewBox="0 0 150 120"><circle cx="60" cy="60" r="38" class="chart-ring-bg"/><circle cx="60" cy="60" r="38" class="chart-ring" pathLength="100" stroke-dasharray="${first} ${100-first}" transform="rotate(-90 60 60)"/>${n.includes('donut')?'<circle cx="60" cy="60" r="23" class="surface-fill"/>':''}</svg><div class="chart-mini-legend">${valid.slice(0,4).map((r,i)=>`<span><i class="c${i}"></i>${esc(r.label)} <b>${num(r.v,'—')}</b></span>`).join('')}</div></div>`,'Chart');
  }
  if(n.includes('horizontal bar')){
    return shell(entry,`<div class="hbar-chart">${valid.slice(0,6).map(r=>`<div><span>${esc(r.label)}</span><i><b style="width:${r.v===null?0:Math.max(2,Math.abs(r.v)/max*100)}%"></b></i><em>${num(r.v)}</em></div>`).join('')}</div>`,'Chart');
  }
  if(n.includes('bar')||n.includes('histogram')||n.includes('pareto')||n.includes('waterfall')){
    const bw=plotW/Math.max(1,valid.length)*.62;
    const bars=valid.map((r,i)=>{const h=r.v===null?0:Math.abs(r.v)/max*plotH;const x=left+(i+.5)*plotW/Math.max(1,valid.length)-bw/2;return `<rect data-behavior-point="${i}" x="${x.toFixed(2)}" y="${(top+plotH-h).toFixed(2)}" width="${bw.toFixed(2)}" height="${h.toFixed(2)}" rx="3" class="${i===valid.length-1?'accent-fill':'soft-fill'}"/>`;}).join('');
    const pareto=n.includes('pareto')?`<path d="${valid.map((r,i)=>`${i?'L':'M'} ${(left+(i+.5)*plotW/valid.length).toFixed(1)} ${(top+plotH-(i+1)/valid.length*plotH*.85).toFixed(1)}`).join(' ')}" class="accent-line"/>`:'';
    return shell(entry,`<svg class="viz-svg" viewBox="0 0 ${W} ${H}"><path class="gridline" d="M${left} ${top+plotH}H${W-right} M${left} ${top+plotH*.5}H${W-right}"/>${bars}${pareto}</svg>`,'Chart');
  }
  if(n.includes('scatter')||n.includes('bubble')||n.includes('strip')||n.includes('dot')){
    const dots=valid.map((r,i)=>{const x=left+(i+.5)*plotW/Math.max(1,valid.length),y=r.v===null?top+plotH:top+plotH-(r.v-min)/Math.max(1,max-min)*plotH;return `<circle data-behavior-point="${i}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${n.includes('bubble')?4+(i%4)*1.5:4}" class="accent-fill"/>`;}).join('');
    return shell(entry,`<svg class="viz-svg" viewBox="0 0 ${W} ${H}"><path class="gridline" d="M${left} ${top}V${top+plotH}H${W-right} M${left} ${top+plotH*.5}H${W-right}"/>${dots}${n.includes('regression')?`<path d="M${left+5} ${top+plotH-5}L${W-right-5} ${top+8}" class="accent-line"/>`:''}</svg>`,'Chart');
  }
  if(n.includes('box')) return shell(entry,`<div class="boxplot-live">${[.32,.48,.67].map((x,i)=>`<span style="--x:${x*100}%"><i></i><b></b><em></em></span>`).join('')}</div><div class="metric-meta"><span>P25 · Median · P75</span><span>Distribution</span></div>`,'Chart');
  if(n.includes('violin')) return shell(entry,`<svg class="viz-svg" viewBox="0 0 ${W} ${H}"><path d="M130 10 C92 24 92 42 112 57 C88 72 95 96 130 110 C165 96 172 72 148 57 C168 42 168 24 130 10Z" class="violin-fill"/><path d="M130 12V108 M112 58H148" class="accent-line"/></svg>`,'Chart');
  if(n.includes('treemap')) return shell(entry,`<div class="treemap-live"><span class="t1">${esc(valid[0]?.label||'A')}</span><span class="t2">${esc(valid[1]?.label||'B')}</span><span class="t3">${esc(valid[2]?.label||'C')}</span><span class="t4">${esc(valid[3]?.label||'D')}</span></div>`,'Chart');
  if(n.includes('funnel')) return shell(entry,`<div class="funnel-live">${valid.slice(0,4).map((r,i)=>`<div style="--w:${100-i*17}%"><b>${esc(r.label)}</b><span>${num(r.v)}</span></div>`).join('')}</div>`,'Chart');
  if(n.includes('sankey')) return shell(entry,`<svg class="viz-svg sankey-live" viewBox="0 0 ${W} ${H}"><rect x="16" y="20" width="10" height="78" rx="3"/><rect x="234" y="16" width="10" height="42" rx="3"/><rect x="234" y="72" width="10" height="32" rx="3"/><path d="M26 35 C105 35 152 22 234 30"/><path d="M26 67 C108 67 151 86 234 86"/></svg>`,'Chart');
  const points=valid.map((r,i)=>{const x=left+i*plotW/Math.max(1,valid.length-1);const y=r.v===null?null:top+plotH-(r.v-min)/Math.max(1,max-min)*plotH;return {x,y};});
  const segments=[];let current=[];for(const p of points){if(p.y===null){if(current.length)segments.push(current);current=[];}else current.push(p);}if(current.length)segments.push(current);
  const area=n.includes('area');
  const lines=segments.map(seg=>{const d=seg.map((p,i)=>`${i?'L':'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');const a=area?`<path d="M${seg[0].x} ${top+plotH} ${seg.map(p=>`L${p.x} ${p.y}`).join(' ')} L${seg.at(-1).x} ${top+plotH}Z" class="chart-area"/>`:'';return `${a}<path d="${d}" class="accent-line"/>`;}).join('');
  return shell(entry,`<svg class="viz-svg" viewBox="0 0 ${W} ${H}"><path class="gridline" d="M${left} ${top+plotH}H${W-right} M${left} ${top+plotH*.5}H${W-right}"/>${lines}${points.filter(p=>p.y!==null).map((p,index)=>`<circle data-behavior-point="${index}" cx="${p.x}" cy="${p.y}" r="3" class="accent-fill"/>`).join('')}</svg>`,'Chart');
}

function engineeringEmpty(entry,n,W,H){
  const note='<small class="empty-hint">Add observations</small>';
  if(n.includes('spc control')) return shell(entry,`<svg class="viz-svg eng-spc" viewBox="0 0 ${W} ${H}"><path d="M18 25H260M18 96H260"/><path d="M18 63L52 58L86 68L120 54L154 61L188 49L222 57L254 52"/>${[52,86,120,154,188,222].map((x,i)=>`<circle cx="${x}" cy="${[58,68,54,61,49,57][i]}" r="3"/>`).join('')}</svg>${note}`,'Engineering');
  if(n.includes('i-mr')) return shell(entry,`<div class="eng-split"><svg viewBox="0 0 220 52"><path d="M8 38L42 29L76 34L110 19L144 28L180 15L212 24"/></svg><svg viewBox="0 0 220 52"><path d="M8 31L42 18L76 36L110 22L144 27L180 14L212 33"/></svg></div>${note}`,'Engineering');
  if(n.includes('xbar-r')) return shell(entry,`<div class="eng-xbar"><section><b>X̄</b><i></i><span></span></section><section><b>R</b><i></i><span></span><span></span></section></div>${note}`,'Engineering');
  if(n.includes('cusum')) return shell(entry,`<svg class="viz-svg eng-cusum" viewBox="0 0 ${W} ${H}"><path d="M18 92L48 86L78 77L108 65L138 49L168 42L198 26L228 17L258 12"/><path d="M18 104L258 28"/></svg>${note}`,'Engineering');
  if(n.includes('ewma')) return shell(entry,`<svg class="viz-svg eng-ewma" viewBox="0 0 ${W} ${H}"><path class="raw" d="M18 85L48 49L78 74L108 38L138 67L168 32L198 53L228 24L258 41"/><path class="smooth" d="M18 79C64 70 80 62 108 57S166 49 198 42S238 36 258 34"/></svg>${note}`,'Engineering');
  if(n.includes('main effects')) return shell(entry,`<div class="eng-effects"><section><b>A</b><i class="up"></i></section><section><b>B</b><i class="down"></i></section><section><b>C</b><i class="flat"></i></section></div>${note}`,'Engineering');
  if(n.includes('interaction plot')) return shell(entry,`<svg class="viz-svg eng-interaction" viewBox="0 0 ${W} ${H}"><path d="M30 88L240 28"/><path d="M30 34L240 82"/><circle cx="30" cy="88" r="3"/><circle cx="240" cy="28" r="3"/><circle cx="30" cy="34" r="3"/><circle cx="240" cy="82" r="3"/></svg>${note}`,'Engineering');
  if(n.includes('residual')) return shell(entry,`<svg class="viz-svg eng-residual" viewBox="0 0 ${W} ${H}"><path d="M18 61H260"/>${[[35,48],[62,72],[91,55],[124,82],[158,43],[194,67],[232,52]].map(([x,y])=>`<circle cx="${x}" cy="${y}" r="3"/>`).join('')}</svg>${note}`,'Engineering');
  if(n.includes('predicted vs actual')) return shell(entry,`<svg class="viz-svg eng-predactual" viewBox="0 0 ${W} ${H}"><path d="M24 100L250 12"/>${[[48,87],[78,70],[112,63],[147,43],[184,38],[220,23]].map(([x,y])=>`<circle cx="${x}" cy="${y}" r="3.5"/>`).join('')}</svg>${note}`,'Engineering');
  if(n.includes('confidence interval')) return shell(entry,`<div class="eng-ci">${[35,58,44,70].map((w,i)=>`<span><i style="width:${w}%"></i><b style="left:${40+i*8}%"></b></span>`).join('')}</div>${note}`,'Engineering');
  if(n.includes('error-bar')) return shell(entry,`<div class="eng-errorbars">${[42,68,54,78].map((h,i)=>`<span style="height:${h}%"><i></i><b></b></span>`).join('')}</div>${note}`,'Engineering');
  return shell(entry,`<div class="data-empty-state full"><b>No observations</b><span>Add engineering data in the inspector.</span></div>`,'Engineering');
}

function engineering(entry){
  const n=entry.element.toLowerCase(),obs=Array.isArray(entry.observations)?entry.observations:[],values=obs.map(x=>typeof x?.value==='number'?x.value:null),nums=values.filter(x=>x!==null),max=Math.max(1,...nums),min=Math.min(0,...nums),W=270,H=122,left=20,right=10,top=10,bottom=20,pw=W-left-right,ph=H-top-bottom;
  const rows=Array.isArray(entry.analysis_rows)?entry.analysis_rows:[],fields=Array.isArray(entry.analysis_fields)?entry.analysis_fields:[],mapping=entry.analysis_mapping||{};
  const fieldName=role=>fields.find(field=>field.id===mapping[role])?.name||null;
  const finite=value=>typeof value==='number'&&Number.isFinite(value);
  const response=fieldName('value');
  const mappedNumerical=[fieldName('x'),fieldName('y')].filter((name,index,list)=>name&&name!==response&&list.indexOf(name)===index);
  const numerical=mappedNumerical.length?mappedNumerical:fields.filter(field=>['integer','number'].includes(field.type)).map(field=>field.name).filter(name=>name&&name!==response);
  const categorical=fields.filter(field=>!['integer','number'].includes(field.type)).map(field=>field.name).filter(Boolean);
  const renderAnalysis=(analysisType,input,options={})=>{try{const plan=prepareEngineeringChart(analysisType,input,{title:entry.title||entry.element,...options});return shell(entry,renderEngineeringChartSvg(plan,{width:300,height:150}),'Engineering');}catch{return null;}};
  if(rows.length&&response){
    if(n.includes('main effects')){const result=renderAnalysis('doe_main',{rows},{factors:categorical.slice(0,3),response});if(result)return result;}
    if(n.includes('interaction plot')){const [factorA,factorB]=categorical;const result=factorA&&factorB&&renderAnalysis('doe_interaction',{rows},{factorA,factorB,response});if(result)return result;}
    if(n.includes('response surface')||n.includes('contour')){const [x1,x2]=numerical;const result=x1&&x2&&renderAnalysis(n.includes('contour')?'contour':'surface',{rows},{x1,x2,response});if(result)return result;}
    if(n.includes('residual')||n.includes('predicted vs actual')){const usable=rows.filter(row=>finite(row[response])&&numerical.every(name=>finite(row[name])));const result=usable.length>=3&&numerical.length&&renderAnalysis(n.includes('residual')?'residual':'predicted',{features:usable.map(row=>numerical.map(name=>row[name])),response:usable.map(row=>row[response])});if(result)return result;}
    if(n.includes('confidence interval')){const group=fieldName('category')||fieldName('series')||categorical[0];const grouped=new Map();rows.forEach(row=>{if(group&&finite(row[response])){const key=String(row[group]??'Unspecified');if(!grouped.has(key))grouped.set(key,[]);grouped.get(key).push(row[response]);}});const result=grouped.size&&renderAnalysis('ci',{groups:[...grouped].map(([label,groupValues])=>({label,values:groupValues}))});if(result)return result;}
    if(n.includes('error-bar')){const label=fieldName('category')||fieldName('series')||categorical[0],lower=fieldName('lower_limit'),upper=fieldName('upper_limit');const groups=lower&&upper?rows.filter(row=>finite(row[response])&&finite(row[lower])&&finite(row[upper])).map((row,index)=>({label:String(row[label]??index+1),value:row[response],lower:row[lower],upper:row[upper]})):[];const result=groups.length&&renderAnalysis('errorbar',{groups});if(result)return result;}
  }
  const type=n.includes('i-mr')?'imr':n.includes('xbar-r')?'xbarr':n.includes('cusum')?'cusum':n.includes('ewma')?'ewma':n.includes('spc')?'spc':null;
  if(type&&nums.length>=2){try{const plan=prepareEngineeringChart(type,type==='xbarr'?{subgroups:entry.subgroups}:{values:nums},{title:entry.title||entry.element,lsl:entry.specification_low,usl:entry.specification_high});return shell(entry,renderEngineeringChartSvg(plan,{width:300,height:150}),'Engineering');}catch{/* invalid analytical input falls through to a visible non-analytical state */}}
  if(!nums.length && !n.includes('response surface') && !n.includes('contour')) return engineeringEmpty(entry,n,W,H);
  if(n.includes('response surface')) return shell(entry,`<div class="surface3d-live">${Array.from({length:49},(_,i)=>`<span style="--x:${i%7};--y:${Math.floor(i/7)};--z:${((i%7)-3)**2+((Math.floor(i/7))-3)**2}"></span>`).join('')}</div><div class="metric-meta"><span>Factor A × Factor B</span><span>Response</span></div>`,'Engineering');
  if(n.includes('contour')) return shell(entry,`<svg class="viz-svg contour-live" viewBox="0 0 ${W} ${H}"><ellipse cx="135" cy="61" rx="92" ry="43"/><ellipse cx="135" cy="61" rx="64" ry="30"/><ellipse cx="135" cy="61" rx="36" ry="17"/><circle cx="148" cy="54" r="4" class="accent-fill"/></svg><div class="metric-meta"><span>Operating window</span><span>Optimum marked</span></div>`,'Engineering');
  const pts=values.map((v,i)=>({x:left+i*pw/Math.max(1,values.length-1),y:v===null?null:top+ph-(v-min)/Math.max(1,max-min)*ph}));
  const path=pts.filter(p=>p.y!==null).map((p,i)=>`${i?'L':'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const lcl=entry.lcl??entry.lower_limit,ucl=entry.ucl??entry.upper_limit;
  const limit=v=>typeof v==='number'?top+ph-(v-min)/Math.max(1,max-min)*ph:null;
  return shell(entry,`<svg class="viz-svg engineering-live" viewBox="0 0 ${W} ${H}"><path class="gridline" d="M${left} ${top+ph}H${W-right} M${left} ${top+ph*.5}H${W-right}"/>${limit(ucl)!==null?`<path d="M${left} ${limit(ucl)}H${W-right}" class="limit-line"/>`:''}${limit(lcl)!==null?`<path d="M${left} ${limit(lcl)}H${W-right}" class="limit-line"/>`:''}<path d="${path}" class="accent-line"/>${pts.filter(p=>p.y!==null).map(p=>`<circle cx="${p.x}" cy="${p.y}" r="3.3" class="accent-fill"/>`).join('')}</svg><div class="metric-meta"><span>${obs.length} observations</span><span>${esc(entry.role||'measurement')}</span></div>`,'Engineering');
}


function interaction(entry){
  const n=entry.element.toLowerCase();
  if(n.includes('tooltip')) return shell(entry,`<div class="interaction-stage"><i class="hover-dot"></i><div class="tooltip-demo"><b>Yield</b><span>98.7%</span><small>Lot 24-118</small></div></div>`,'Interaction');
  if(n.includes('cross-filter')) return shell(entry,`<div class="crossfilter-live"><div>${['A','B','C','D'].map((x,i)=>`<i class="${i===1?'active':''}" style="height:${28+i*13}px"></i>`).join('')}</div><span>Selection filters linked evidence</span></div>`,'Interaction');
  if(n.includes('brush')||n.includes('range')) return shell(entry,`<div class="range-live"><div></div><i class="start"></i><i class="end"></i><b></b></div><div class="metric-meta"><span>Selected range</span><span>12 → 38</span></div>`,'Interaction');
  if(n.includes('drill')) return shell(entry,`<div class="drill-live"><span>Fab</span><i>›</i><span>Etch</span><i>›</i><b>Chamber A</b></div><p class="body-copy">Double-click a mark to move one level deeper.</p>`,'Interaction');
  if(n.includes('tabs')) return shell(entry,`<div class="tabs-live"><b>Overview</b><span>Evidence</span><span>Actions</span></div><div class="tab-surface-live"></div>`,'Interaction');
  if(n.includes('expand')) return shell(entry,`<div class="expand-live"><b>Root cause evidence</b><span>⌄</span></div><div class="expand-detail-live">Pressure excursion aligns with defect onset.</div>`,'Interaction');
  if(n.includes('count')) return shell(entry,`<div class="countup-live">42<span>.8</span></div><div class="metric-meta"><span>Animated transition</span><span>reduced motion aware</span></div>`,'Interaction');
  if(n.includes('reveal')) return shell(entry,`<div class="reveal-live"><i></i><i></i><i></i><i></i><span>Reveal series progressively</span></div>`,'Interaction');
  if(n.includes('timeline')) return shell(entry,`<div class="interactive-timeline-live">${['Collect','Analyze','Decide'].map((x,i)=>`<button tabindex="-1" class="${i===1?'active':''}"><i></i><span>${x}</span></button>`).join('')}</div>`,'Interaction');
  if(n.includes('hover')) return shell(entry,`<div class="hover-highlight-live"><span></span><span class="active"></span><span></span><span></span></div><div class="metric-meta"><span>Pointer focus</span><span>keyboard equivalent</span></div>`,'Interaction');
  return shell(entry,`<div class="interaction-stage"><b>${esc(entry.element)}</b><span>Interactive behavior preview</span></div>`,'Interaction');
}
function infrastructure(entry){
  const n=entry.element.toLowerCase();
  if(n.includes('selection box')) return shell(entry,`<div class="infra-stage selection-infra"><div><i></i><i></i><i></i><i></i></div></div>`,'Editor');
  if(n.includes('resize')) return shell(entry,`<div class="infra-stage resize-infra"><div><i></i><i></i><i></i><i></i></div><span>Drag handles</span></div>`,'Editor');
  if(n.includes('smart guide')) return shell(entry,`<div class="infra-stage guides-infra smart-guides-live"><div></div><span></span><i></i><b>14</b></div>`,'Editor');
  if(n.includes('snap line')) return shell(entry,`<div class="infra-stage snap-lines-live"><div></div><span></span><i></i><em></em></div>`,'Editor');
  if(n.includes('drop zone')) return shell(entry,`<div class="dropzone-live"><b>Drop element here</b><span>14px insertion target</span></div>`,'Editor');
  if(n.includes('ghost')) return shell(entry,`<div class="ghost-live"><div></div><div class="ghost"></div></div>`,'Editor');
  if(n.includes('multi-select')) return shell(entry,`<div class="infra-stage multiselect-live"><i></i><i></i><i></i><b></b></div>`,'Editor');
  if(n.includes('group')) return shell(entry,`<div class="group-live"><span>A</span><span>B</span><i></i></div>`,'Editor');
  if(n.includes('lock')) return shell(entry,`<div class="lock-live"><i>⌑</i><b>Locked</b><span>Geometry protected</span></div>`,'Editor');
  if(n.includes('layer')) return shell(entry,`<div class="layers-live"><i></i><i></i><i></i></div>`,'Editor');
  if(n.includes('auto-layout')) return shell(entry,`<div class="autolayout-live"><span></span><span></span><span></span><i>14</i><i>14</i></div>`,'Editor');
  if(n.includes('align')||n.includes('distribute')) return shell(entry,`<div class="align-live"><i></i><span></span><span></span><span></span></div>`,'Editor');
  if(n.includes('zoom')||n.includes('pan')) return shell(entry,`<div class="zoom-live"><button tabindex="-1">−</button><b>81%</b><button tabindex="-1">+</button><span>Fit</span></div>`,'Editor');
  if(n.includes('mini-map')) return shell(entry,`<div class="minimap-live"><i></i><i></i><i></i><b></b></div>`,'Editor');
  if(n.includes('undo')) return shell(entry,`<div class="history-live"><button tabindex="-1">↶ Undo</button><button tabindex="-1">↷ Redo</button></div>`,'Editor');
  if(n.includes('command')) return shell(entry,`<div class="command-live"><span>⌘K</span><b>Search commands…</b></div>`,'Editor');
  if(n.includes('keyboard')) return shell(entry,`<div class="keys-live"><kbd>⌘K</kbd><kbd>⌘Z</kbd><kbd>⇧</kbd><kbd>Del</kbd></div>`,'Editor');
  if(n.includes('context toolbar')) return shell(entry,`<div class="context-live"><span>Lock</span><span>Group</span><span>Front</span><b>Delete</b></div>`,'Editor');
  if(n.includes('right inspector')) return shell(entry,`<div class="inspector-live"><b>Identity</b><span></span><b>Data</b><span></span><span></span></div>`,'Editor');
  if(n.includes('paste data')) return shell(entry,`<div class="paste-live"><b>⌘V</b><span>Paste TSV / CSV</span><small>Missing stays missing</small></div>`,'Editor');
  if(n.includes('chart switcher')) return shell(entry,`<div class="switcher-live"><b>Line</b><span>Bar</span><span>Scatter</span></div>`,'Editor');
  if(n.includes('suggestion')) return shell(entry,`<div class="suggestions-live"><span>Editorial Bento</span><span>Executive</span><span>Technical</span></div>`,'Editor');
  if(n.includes('preset')) return shell(entry,`<div class="preset-live"><b>My preset</b><span>Save current report</span><i>✓</i></div>`,'Editor');
  return shell(entry,`<div class="infra-stage"><b>${esc(entry.element)}</b></div>`,'Editor');
}

export function renderIntegratedElement(entry){
  switch(entry.engine){
    case 'TextEngine': return text(entry);
    case 'CoreChartEngine': return chart(entry);
    case 'EngineeringChartEngine': return engineering(entry);
    case 'SmartLayoutEngine': return smartLayout(entry);
    case 'MetricEngine': return metric(entry);
    case 'ComparisonEngine': return comparison(entry);
    case 'TableEngine': return table(entry);
    case 'MatrixEngine': return matrix(entry);
    case 'TimelineEngine': return timeline(entry);
    case 'DiagramEngine': return diagram(entry);
    case 'ImageMediaEngine': return image(entry);
    case 'EvidenceCompositeEngine': case 'DecisionCompositeEngine': case 'ProjectCompositeEngine': return composite(entry);
    case 'WaferFabEngine': return wafer(entry);
    case 'InteractionLayer': return interaction(entry);
    case 'EditorInfrastructure': return infrastructure(entry);
    default: return renderFrozenElement(entry.element,entry.engine,{tier:'production'}).replace(/<span class="quality-badge">[^<]*<\/span>/,'').replace('gallery-card ',`gallery-card integrated-variant variant-${slug(entry.element)} `);
  }
}
