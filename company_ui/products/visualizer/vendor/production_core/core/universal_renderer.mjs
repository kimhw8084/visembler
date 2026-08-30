import { ELEMENTS_BY_ENGINE } from './runtime_registry.mjs';

const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const slug = value => String(value).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
const bars = [66,42,83,55,72,48];
const linePts = [[6,71],[24,58],[42,62],[60,38],[78,46],[94,21]];
const spark = `<svg class="mini-svg" viewBox="0 0 100 50" role="img" aria-label="Trend sparkline"><path class="gridline" d="M0 42H100 M0 22H100"/><path class="accent-line" d="M3 39 L20 31 L37 35 L54 21 L71 24 L97 8"/></svg>`;

function chartSvg(name){
  const n=name.toLowerCase();
  if(n.includes('pie')||n.includes('donut')) return `<svg class="viz-svg" viewBox="0 0 220 112" role="img" aria-label="${esc(name)} preview"><circle cx="68" cy="56" r="36" class="chart-ring-bg"/><circle cx="68" cy="56" r="36" class="chart-ring" pathLength="100" stroke-dasharray="68 32" transform="rotate(-90 68 56)"/>${n.includes('donut')?'<circle cx="68" cy="56" r="21" class="surface-fill"/>':''}<g class="legend"><rect x="126" y="26" width="10" height="10" rx="3"/><text x="143" y="35">Primary 68%</text><rect x="126" y="50" width="10" height="10" rx="3" class="muted-fill"/><text x="143" y="59">Secondary 21%</text><rect x="126" y="74" width="10" height="10" rx="3" class="line-fill"/><text x="143" y="83">Other 11%</text></g></svg>`;
  if(n.includes('scatter')||n.includes('bubble')||n.includes('strip')||n.includes('dot')) return `<svg class="viz-svg" viewBox="0 0 220 112" role="img" aria-label="${esc(name)} preview"><path class="gridline" d="M24 12V94H210 M24 30H210 M24 52H210 M24 74H210"/>${[[42,74,5],[66,64,7],[91,55,4],[119,58,8],[143,40,5],[171,31,9],[194,21,5]].map(([x,y,r])=>`<circle cx="${x}" cy="${y}" r="${n.includes('bubble')?r:4}" class="accent-fill"/>`).join('')}${n.includes('regression')?'<path d="M34 80L201 18" class="accent-line"/>':''}</svg>`;
  if(n.includes('histogram')||n.includes('bar')||n.includes('pareto')||n.includes('waterfall')) return `<svg class="viz-svg" viewBox="0 0 220 112" role="img" aria-label="${esc(name)} preview"><path class="gridline" d="M20 94H212 M20 72H212 M20 50H212 M20 28H212"/>${bars.map((h,i)=>`<rect x="${28+i*30}" y="${94-h*.72}" width="20" height="${h*.72}" rx="4" class="${i===4?'accent-fill':'soft-fill'}"/>`).join('')}${n.includes('pareto')?'<path d="M38 72 L68 58 L98 43 L128 31 L158 24 L188 17" class="accent-line"/>':''}</svg>`;
  if(n.includes('treemap')) return `<svg class="viz-svg" viewBox="0 0 220 112" role="img" aria-label="Treemap preview"><rect x="8" y="8" width="91" height="60" rx="6" class="accent-fill"/><rect x="103" y="8" width="109" height="36" rx="6" class="soft-fill"/><rect x="103" y="48" width="54" height="56" rx="6" class="line-fill"/><rect x="161" y="48" width="51" height="56" rx="6" class="soft-fill"/><text x="16" y="28" class="svg-on-accent">A · 42%</text></svg>`;
  if(n.includes('funnel')) return `<svg class="viz-svg" viewBox="0 0 220 112" role="img" aria-label="Funnel preview"><path d="M20 12H200L174 38H46Z" class="accent-fill"/><path d="M48 42H172L150 67H70Z" class="soft-fill"/><path d="M73 71H147L131 96H89Z" class="line-fill"/><text x="110" y="30" text-anchor="middle" class="svg-on-accent">100%</text></svg>`;
  if(n.includes('sankey')) return `<svg class="viz-svg" viewBox="0 0 220 112" role="img" aria-label="Sankey preview"><rect x="12" y="22" width="16" height="64" rx="4" class="accent-fill"/><rect x="104" y="14" width="16" height="38" rx="4" class="soft-fill"/><rect x="104" y="64" width="16" height="34" rx="4" class="line-fill"/><rect x="192" y="31" width="16" height="50" rx="4" class="accent-fill"/><path d="M28 32 C64 32 70 22 104 22 M28 62 C67 62 70 77 104 77 M120 31 C156 31 158 46 192 46 M120 80 C156 80 158 67 192 67" class="sankey-flow"/></svg>`;
  if(n.includes('box')||n.includes('violin')) return `<svg class="viz-svg" viewBox="0 0 220 112" role="img" aria-label="${esc(name)} preview"><path class="gridline" d="M24 94H210 M24 72H210 M24 50H210 M24 28H210"/>${[65,110,155].map((x,i)=>n.includes('violin')?`<path d="M${x} 18 C${x-20} 36 ${x-18} 72 ${x} 93 C${x+18} 72 ${x+20} 36 ${x} 18Z" class="soft-fill"/><path d="M${x} 28V84" class="accent-line"/>`:`<path d="M${x} 20V92 M${x-14} 34H${x+14}V76H${x-14}Z M${x-14} 55H${x+14}" class="chart-stroke"/>`).join('')}</svg>`;
  return `<svg class="viz-svg" viewBox="0 0 220 112" role="img" aria-label="${esc(name)} preview"><path class="gridline" d="M20 94H212 M20 72H212 M20 50H212 M20 28H212"/><path d="${linePts.map(([x,y],i)=>`${i?'L':'M'} ${20+x*1.9} ${y}`).join(' ')}" class="accent-line"/>${linePts.map(([x,y])=>`<circle cx="${20+x*1.9}" cy="${y}" r="3.6" class="accent-fill"/>`).join('')}</svg>`;
}

function engineeringSvg(name){
 const n=name.toLowerCase();
 if(n.includes('contour')||n.includes('response surface')) return `<svg class="viz-svg" viewBox="0 0 220 112" role="img" aria-label="${esc(name)} preview"><rect x="18" y="12" width="186" height="88" rx="8" class="soft-fill"/><ellipse cx="112" cy="55" rx="74" ry="32" class="contour contour1"/><ellipse cx="112" cy="55" rx="50" ry="22" class="contour contour2"/><ellipse cx="112" cy="55" rx="25" ry="12" class="contour contour3"/></svg>`;
 if(n.includes('error')||n.includes('confidence')) return `<svg class="viz-svg" viewBox="0 0 220 112" role="img" aria-label="${esc(name)} preview">${[45,80,115,150,185].map((x,i)=>`<path d="M${x} ${28+i*8}V${72+i*3} M${x-7} ${28+i*8}H${x+7} M${x-7} ${72+i*3}H${x+7}" class="chart-stroke"/><circle cx="${x}" cy="${50+i*5}" r="5" class="accent-fill"/>`).join('')}</svg>`;
 return chartSvg(name);
}

function tableBody(name){
 const dense=name.toLowerCase().includes('dense');
 return `<div class="table-frame"><table aria-label="${esc(name)} sample"><thead><tr><th>Item</th><th>Status</th><th class="num">Value</th></tr></thead><tbody>${['Alpha','Beta','Gamma',dense?'Delta':''].filter(Boolean).map((x,i)=>`<tr><td>${x}</td><td><span class="state ${i===2?'warn':'good'}">${i===2?'Watch':'On track'}</span></td><td class="num">${[92,87,71,64][i]}</td></tr>`).join('')}</tbody></table></div>`;
}
function matrixBody(name){return `<div class="matrix" role="grid" aria-label="${esc(name)} preview">${Array.from({length:16},(_,i)=>`<div role="gridcell" class="matrix-cell level-${(i*7)%5}">${i%5===0?'High':i%3===0?'Med':'Low'}</div>`).join('')}</div>`;}
function timelineBody(name){
 const vertical=name.toLowerCase().includes('vertical');
 return `<div class="timeline-${vertical?'vertical':'rail'}" role="list" aria-label="${esc(name)} preview">${['Discover','Validate','Implement','Verify'].map((x,i)=>`<div role="listitem" class="tl-step ${i<2?'done':''}"><span class="tl-dot"></span><div><b>${x}</b><small>${i===0?'Aug 12':i===1?'Aug 19':i===2?'Aug 27':'Sep 04'}</small></div></div>`).join('')}</div>`;
}
function diagramBody(name){
 const nodes=['Source','Transform','Decision','Output'];
 return `<svg class="diagram-svg" viewBox="0 0 260 116" role="img" aria-label="${esc(name)} preview"><defs><marker id="arr-${slug(name)}" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L8 4L0 8Z" class="accent-fill"/></marker></defs>${nodes.map((x,i)=>`<rect x="${8+i*64}" y="${i%2?54:20}" width="52" height="32" rx="8" class="node-box"/><text x="${34+i*64}" y="${i%2?73:39}" text-anchor="middle" class="node-text">${x}</text>`).join('')}${[0,1,2].map(i=>`<path d="M${60+i*64} ${i%2?70:36} C${75+i*64} ${i%2?70:36}, ${77+i*64} ${(i+1)%2?70:36}, ${72+(i+1)*64} ${(i+1)%2?70:36}" class="accent-line connector" marker-end="url(#arr-${slug(name)})"/>`).join('')}</svg>`;
}
function imageBody(name){return `<div class="media-demo" role="img" aria-label="${esc(name)} preview"><div class="media-grid"></div><div class="media-focus"></div><div class="media-callout"><b>Critical region</b><span>Asset-relative annotation</span></div></div>`;}
function waferBody(name){const cells=[];for(let y=-4;y<=4;y++)for(let x=-5;x<=5;x++){if(x*x+y*y<28){const m=(x*3+y*5+30)%5;cells.push(`<span class="die heat-${m}" style="--x:${x+5};--y:${y+4}" title="Die ${x},${y}"></span>`);}}return `<div class="wafer-demo" role="img" aria-label="${esc(name)} preview"><div class="wafer-grid">${cells.join('')}</div><span class="wafer-notch"></span></div>`;}
function metricBody(name){
 const ring=name.toLowerCase().includes('ring');
 if(ring) return `<div class="metric-ring"><svg viewBox="0 0 100 100" role="img" aria-label="84 percent"><circle cx="50" cy="50" r="38" class="chart-ring-bg"/><circle cx="50" cy="50" r="38" class="chart-ring" pathLength="100" stroke-dasharray="84 16" transform="rotate(-90 50 50)"/></svg><b>84%</b></div><p class="muted">Yield confidence</p>`;
 return `<div class="metric-value">${name.includes('Rate')?'98.7%':name.includes('Capacity')?'1.42M':'42.8'}</div><div class="metric-meta"><span class="state good">▲ 6.4%</span><span>vs target</span></div>${name.includes('Sparkline')?spark:''}<div class="meter"><span style="width:${name.includes('Threshold')?72:84}%"></span></div>`;
}
function textBody(name){
 if(name.includes('Hero')) return `<div class="hero-copy">Operational clarity at production speed.</div><p class="muted">A disciplined narrative hierarchy with governed line length and readable type floors.</p>`;
 if(name.includes('Quote')) return `<blockquote>“The decision is clear when evidence and consequence are visible together.”</blockquote><p class="muted">— Review synthesis</p>`;
 if(name.includes('Code')) return `<pre><code>yield = good_dies / tested_dies\nassert yield &gt;= target</code></pre>`;
 if(name.includes('Narrative Sequence')) return `<ol class="sequence"><li>Observe the signal</li><li>Test the mechanism</li><li>Lock the action</li></ol>`;
 return `<p class="body-copy">A concise, evidence-bound explanation that preserves hierarchy, provenance, and readability across output sizes.</p><p class="source-line">Source · Production evidence · Updated Aug 27</p>`;
}
function comparisonBody(name){return `<div class="comparison"><div><span class="eyebrow">Before</span><b>62%</b><small>Manual path</small></div><span class="compare-arrow">→</span><div><span class="eyebrow">After</span><b>91%</b><small>Governed path</small></div></div>`;}
function compositeBody(name,kind){
 const tone=kind==='EvidenceCompositeEngine'?'Evidence':kind==='DecisionCompositeEngine'?'Decision':'Delivery';
 return `<div class="composite-hero"><span class="eyebrow">${tone}</span><strong>${esc(name)}</strong><p>${kind==='EvidenceCompositeEngine'?'Supported by three independent signals; one contradiction remains open.':kind==='DecisionCompositeEngine'?'Recommended path balances impact, reversibility, and implementation risk.':'Workstream is on track with one upcoming dependency.'}</p></div><div class="chip-row"><span class="state good">Verified</span><span class="chip">Owner · J. Kim</span><span class="chip">High impact</span></div>`;
}
function layoutBody(name){return `<div class="layout-demo ${slug(name)}" aria-label="${esc(name)} layout preview">${Array.from({length:name.includes('Masonry')?5:4},(_,i)=>`<span class="layout-block b${i+1}"></span>`).join('')}</div>`;}
function interactionBody(name){
 const n=name.toLowerCase();
 if(n.includes('tabs')) return `<div class="demo-tabs" role="tablist" aria-label="${esc(name)}"><button role="tab" aria-selected="true">Overview</button><button role="tab">Evidence</button><button role="tab">Risks</button></div><p class="body-copy">Selected tab content remains keyboard reachable.</p>`;
 if(n.includes('brush')||n.includes('range')) return `<div class="range-demo"><span class="range-fill"></span><button aria-label="Range start" class="range-handle left"></button><button aria-label="Range end" class="range-handle right"></button></div>`;
 return `<button class="demo-action" aria-label="Demonstrate ${esc(name)}">${esc(name)}</button><div class="interaction-feedback" aria-live="polite">Keyboard + pointer ready</div>`;
}
function editorBody(name){
 const n=name.toLowerCase();
 if(n.includes('mini-map')) return `<div class="mini-map-demo">${Array.from({length:6},(_,i)=>`<span style="left:${10+(i%3)*30}%;top:${15+Math.floor(i/3)*42}%;width:${20+i%2*8}%;height:24%"></span>`).join('')}<i></i></div>`;
 if(n.includes('resize')||n.includes('selection')||n.includes('smart guides')||n.includes('snap')) return `<div class="selection-demo"><div class="selected-box"><span></span><span></span><span></span><span></span></div><i class="guide-v"></i><i class="guide-h"></i></div>`;
 return `<div class="editor-demo"><button class="demo-action" aria-label="${esc(name)} action">${esc(name)}</button><kbd>⌘K</kbd><span class="muted">Revision-safe command</span></div>`;
}

export function findEngineForElement(name){for(const [engine,names] of Object.entries(ELEMENTS_BY_ENGINE)) if(names.includes(name)) return engine; return null;}
export function renderElement(name, engine=findEngineForElement(name), options={}){
 if(!engine) throw new Error(`Unknown element: ${name}`);
 let body='';
 switch(engine){
  case 'SmartLayoutEngine': body=layoutBody(name); break;
  case 'TextEngine': body=textBody(name); break;
  case 'MetricEngine': body=metricBody(name); break;
  case 'ComparisonEngine': body=comparisonBody(name); break;
  case 'CoreChartEngine': body=chartSvg(name); break;
  case 'TableEngine': body=tableBody(name); break;
  case 'MatrixEngine': body=matrixBody(name); break;
  case 'TimelineEngine': body=timelineBody(name); break;
  case 'DiagramEngine': body=diagramBody(name); break;
  case 'ImageMediaEngine': body=imageBody(name); break;
  case 'EvidenceCompositeEngine': case 'DecisionCompositeEngine': case 'ProjectCompositeEngine': body=compositeBody(name,engine); break;
  case 'EngineeringChartEngine': body=engineeringSvg(name); break;
  case 'WaferFabEngine': body=waferBody(name); break;
  case 'InteractionLayer': body=interactionBody(name); break;
  case 'EditorInfrastructure': body=editorBody(name); break;
  default: body=`<p>${esc(name)}</p>`;
 }
 const tier=options.tier ?? 'production';
 return `<article class="gallery-card engine-${slug(engine)}" data-element="${esc(name)}" data-engine="${esc(engine)}" tabindex="0" role="group" aria-label="${esc(name)} component preview"><header><div><span class="engine-label">${esc(engine.replace('Engine','').replace('Infrastructure',' Infra'))}</span><h3>${esc(name)}</h3></div><span class="quality-badge">${esc(tier)}</span></header><div class="card-body">${body}</div></article>`;
}
export function renderEngineGallery(engine){return (ELEMENTS_BY_ENGINE[engine]??[]).map(name=>renderElement(name,engine)).join('');}
export function renderAllElements(){return Object.entries(ELEMENTS_BY_ENGINE).flatMap(([engine,names])=>names.map(name=>renderElement(name,engine))).join('');}
