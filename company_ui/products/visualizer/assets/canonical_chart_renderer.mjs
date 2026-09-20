// Canonical production renderer for user-authored core charts.
//
// This module deliberately owns the shared geometry contract.  Chart Studio,
// the report editor and SVG export all call it through renderChartSvg in
// authoring_chart_studio.mjs.  Engineering, statistical and wafer/fab views
// remain specialized because their marks carry domain-specific meaning.

const EPS = 1e-12;
const CORE_TYPES = new Set(['Vertical Bar','Horizontal Bar','Line Chart','Multi-Line','Area Chart','Scatter Plot','Regression Scatter','Histogram','Box Plot','Pareto']);
const BAR_TYPES = new Set(['Vertical Bar','Horizontal Bar']);
const NUMBER_TYPES = new Set(['number','integer']);
const TIME_TYPES = new Set(['date','datetime','time','timestamp']);
const PALETTES = Object.freeze({
  report:['#1769d1','#2e8b72','#b7791f','#9b4dca','#c94f5f','#3b82a0','#6f7c38','#d36c2e','#5b6abf','#168a8a','#8f5b34','#a44778'],
  semantic:['#1769d1','#19734d','#b7791f','#c94f5f','#6f7c38','#9b4dca','#3b82a0','#d36c2e','#1769d1','#19734d','#b7791f','#c94f5f'],
  colorblind:['#0072B2','#E69F00','#009E73','#D55E00','#CC79A7','#56B4E9','#F0E442','#000000','#117733','#882255','#44AA99','#DDCC77'],
});

const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const finite = value => typeof value === 'number' && Number.isFinite(value);
const missing = value => value === null || value === undefined || value === '';
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const field = (model, id) => model.dataset?.fields?.find(item => item.id === id) || null;
const fieldIndex = (model, id) => model.dataset?.fields?.findIndex(item => item.id === id) ?? -1;
const fieldName = (model, id) => field(model, id)?.name || id || '';
const numberLike = type => NUMBER_TYPES.has(type);
const timeLike = type => TIME_TYPES.has(type);
const numericValues = values => values.filter(finite);
const niceStep = (range, count) => {
  const raw = Math.abs(range) / Math.max(1, count - 1);
  if (!finite(raw) || raw <= EPS) return 1;
  const power = 10 ** Math.floor(Math.log10(raw));
  const error = raw / power;
  const factor = error >= 5 ? 10 : error >= 2 ? 5 : error >= 1 ? 2 : 1;
  return factor * power;
};
const shortText = (value, limit=18) => {
  const text = String(value ?? '');
  return text.length > limit ? `${text.slice(0, Math.max(1, limit - 1))}…` : text;
};
const approxTextWidth = (value, fontSize=11) => Math.max(fontSize * 1.4, String(value ?? '').length * fontSize * .58);
const parseTime = value => {
  if (value instanceof Date && Number.isFinite(value.getTime())) return value.getTime();
  if (finite(value)) return value;
  if (typeof value !== 'string' || !value.trim()) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
};
const unique = values => [...new Set(values)];
const compareLabels = (a,b) => String(a).localeCompare(String(b), undefined, {numeric:true, sensitivity:'base'});

function extent(values, configured={}, {zeroBaseline=false, fallback=[0,1]}={}) {
  const nums = numericValues(values);
  let min = finite(configured.min) ? configured.min : (nums.length ? Math.min(...nums) : fallback[0]);
  let max = finite(configured.max) ? configured.max : (nums.length ? Math.max(...nums) : fallback[1]);
  if (zeroBaseline) { min = Math.min(0, min); max = Math.max(0, max); }
  if (!finite(min)) min = fallback[0];
  if (!finite(max)) max = fallback[1];
  if (min === max) { const pad = Math.max(1, Math.abs(min) * .08); min -= pad; max += pad; }
  if (min > max) [min,max] = [max,min];
  return {min,max};
}

function axisFormat(axis, value, {percentDomain=false, temporal=false}={}) {
  if (temporal) {
    const date = new Date(value);
    if (!Number.isNaN(date.getTime())) {
      const iso = date.toISOString();
      return axis.format === 'date' || iso.slice(11,19) === '00:00:00' ? iso.slice(0,10) : `${iso.slice(0,10)} ${iso.slice(11,16)}`;
    }
  }
  if (!finite(value)) return '';
  const precision = Number.isInteger(axis.precision) ? clamp(axis.precision,0,8) : null;
  let result = percentDomain || axis.format === 'percent' ? `${(value * 100).toFixed(precision ?? 1)}%` : precision === null ? (Math.abs(value) >= 1000 ? value.toLocaleString('en-US',{maximumFractionDigits:1}) : String(Number(value.toFixed(4)))) : value.toFixed(precision);
  if (axis.prefix) result = `${axis.prefix}${result}`;
  if (axis.unit) result = `${result} ${axis.unit}`;
  if (axis.suffix) result = `${result}${axis.suffix}`;
  return result;
}

function xLabel(model, raw, value, temporal) {
  if (temporal) return axisFormat(model.axes.x, value, {temporal:true});
  return String(raw ?? '');
}

function numericMapping(model, role) {
  return numberLike(field(model, model.mapping?.[role])?.type);
}

function buildRows(model) {
  const dataset = model.dataset || {fields:[],rows:[]};
  const type = model.chart_type;
  const xRole = type === 'Pareto' || BAR_TYPES.has(type) ? 'category' : model.mapping?.x ? 'x' : model.mapping?.category ? 'category' : model.mapping?.time ? 'time' : null;
  const yRole = type === 'Pareto' || BAR_TYPES.has(type) || type === 'Histogram' || type === 'Box Plot' ? 'value' : model.mapping?.y ? 'y' : 'value';
  const xIndex = fieldIndex(model, model.mapping?.[xRole]);
  const yIndex = fieldIndex(model, model.mapping?.[yRole]);
  const seriesIndex = fieldIndex(model, model.mapping?.series || model.mapping?.color);
  const xField = field(model, model.mapping?.[xRole]);
  const temporal = timeLike(xField?.type) || Boolean(xField?.semantic_tags?.includes('time'));
  const xNumeric = numberLike(xField?.type) || (temporal && (dataset.rows || []).some(row => parseTime(row?.[xIndex]) !== null));
  let rows = (dataset.rows || []).map((row, index) => {
    const xRaw = xIndex >= 0 ? row?.[xIndex] : index;
    const yRaw = yIndex >= 0 ? row?.[yIndex] : null;
    const xValue = xNumeric ? (temporal ? parseTime(xRaw) : (finite(xRaw) ? xRaw : Number(xRaw))) : index;
    const series = seriesIndex >= 0 ? String(row?.[seriesIndex] ?? 'Value') : 'Value';
    return {index,row,xRaw,yRaw,series,xValue,temporal,xNumeric,yMissing:missing(yRaw),y:finite(yRaw) ? yRaw : null};
  });
  const secondaryIndex=fieldIndex(model,model.mapping?.secondaryY);
  if (secondaryIndex>=0 && secondaryIndex!==yIndex && seriesIndex<0) rows=rows.flatMap(base=>[
    base,
    {...base,series:fieldName(model,model.mapping.secondaryY),yRaw:base.row?.[secondaryIndex],yMissing:missing(base.row?.[secondaryIndex]),y:finite(base.row?.[secondaryIndex])?base.row[secondaryIndex]:null,secondary:true},
  ]);
  return {rows,xIndex,yIndex,seriesIndex,xField,temporal,xNumeric,xRole,yRole};
}

function normalizedSeries(model, rows) {
  const names = unique(rows.map(row => row.series));
  const declared = Array.isArray(model.series) ? model.series : [];
  const secondaryNames = new Set([...(model.axes?.secondaryY?.series || []), model.mapping?.secondaryY, fieldName(model, model.mapping?.secondaryY)].filter(Boolean).map(String));
  const palette = PALETTES[model.visual?.palette] || PALETTES.report;
  let ordered = declared.map(item => String(item?.key ?? item?.name ?? item?.label ?? '')).filter(name => names.includes(name));
  ordered = [...ordered, ...names.filter(name => !ordered.includes(name))];
  if (model.legend?.order === 'label-asc') ordered.sort(compareLabels);
  if (model.legend?.order === 'label-desc') ordered.sort((a,b) => compareLabels(b,a));
  if (model.legend?.order === 'value-desc') ordered.sort((a,b) => sumSeries(rows,b)-sumSeries(rows,a));
  return ordered.map((name,index) => {
    const spec = declared.find(item => String(item?.key ?? item?.name ?? item?.label ?? '') === name) || (declared.length === 1 && names.length === 1 ? declared[0] : null);
    const fieldSpec = declared.find(item => item?.field && String(item.field) === String(model.mapping?.secondaryY));
    return {
      key:name,
      name:String(spec?.label || spec?.name || name),
      color:spec?.color || palette[index % palette.length],
      visible:spec?.visible !== false,
      legend:spec?.legend !== false,
      axis:spec?.axis === 'secondary' || secondaryNames.has(name) || (fieldSpec?.axis === 'secondary' && (spec?.field===model.mapping?.secondaryY || name===fieldName(model,model.mapping?.secondaryY))) ? 'secondary' : 'primary',
      lineWidth:finite(spec?.lineWidth) ? clamp(spec.lineWidth,1,8) : model.visual?.lineWidth || 2.5,
      lineDash:spec?.lineDash || model.visual?.lineDash || 'solid',
      smoothing:spec?.smoothing === true || (spec?.smoothing == null && model.visual?.smoothing === true),
      markers:spec?.markers !== false && model.visual?.markers !== false,
    };
  });
}

function sumSeries(rows, name) { return rows.filter(row => row.series === name).reduce((sum,row) => sum + (finite(row.y) ? row.y : 0),0); }

function prepareRows(model, raw) {
  const policy = model.visual?.missingPolicy || 'gap';
  const filtered = policy === 'drop' ? raw.rows.filter(row => !row.yMissing) : raw.rows;
  const labels = raw.xNumeric ? [] : unique(filtered.map(row => String(row.xRaw ?? '')));
  const rowValues = filtered.map(row => ({...row,y:row.yMissing ? (policy === 'zero' ? 0 : null) : row.y}));
  const xNumbers = rowValues.map(row => row.xValue).filter(finite);
  const xDomain = raw.xNumeric ? extent(xNumbers,{min:model.axes?.x?.min,max:model.axes?.x?.max}) : {min:0,max:Math.max(1,labels.length-1)};
  const xKeys = raw.xNumeric ? unique(xNumbers).sort((a,b)=>a-b) : labels;
  const series = normalizedSeries(model,rowValues);
  const bySeries = series.map(spec => xKeys.map((key,keyIndex) => {
    const matches = rowValues.filter(row => row.series === spec.key && (raw.xNumeric ? row.xValue === key : String(row.xRaw ?? '') === key));
    const match = matches.length ? matches.at(-1) : null;
    return {x:raw.xNumeric ? key : keyIndex,xRaw:match?.xRaw ?? key,y:match?.y ?? null,row:match,sourceIndex:match?.index ?? null};
  }));
  return {...raw,rows:rowValues,labels,xDomain,xKeys,series,bySeries};
}

function stackInfo(plan, model) {
  const mode = model.visual?.barMode || 'grouped';
  const totals = plan.xKeys.map((_,index) => {
    let positive=0,negative=0;
    plan.bySeries.forEach((values,seriesIndex) => {
      if (!plan.series[seriesIndex].visible) return;
      const value=values[index]?.y;
      if (!finite(value)) return;
      if (mode === 'percent') { if (value >= 0) positive += value; else negative += Math.abs(value); }
      else if (value >= 0) positive += value; else negative += Math.abs(value);
    });
    return {positive,negative};
  });
  const stacks = plan.bySeries.map((values,seriesIndex) => values.map((point,index) => {
    const value=finite(point.y) ? point.y : null;
    if (value === null) return {value:null,base:0,top:0,display:null};
    if (mode === 'grouped') return {value,base:0,top:value,display:value};
    const total=totals[index],display=mode === 'percent' ? (value >= 0 ? value/Math.max(EPS,total.positive) : -Math.abs(value)/Math.max(EPS,total.negative)) : value;
    const prior=plan.bySeries.slice(0,seriesIndex).reduce((sum,other) => {
      const v=other[index]?.y; if(!finite(v)) return sum;
      if (value >= 0 && v >= 0) return sum + (mode === 'percent' ? v/Math.max(EPS,total.positive) : v);
      if (value < 0 && v < 0) return sum - (mode === 'percent' ? Math.abs(v)/Math.max(EPS,total.negative) : Math.abs(v));
      return sum;
    },0);
    return {value,base:prior,top:prior+display,display};
  }));
  const domainValues = mode === 'grouped' ? plan.bySeries.flatMap(values => values.map(point => point.y)) : mode === 'percent' ? totals.flatMap(total => [total.positive ? 1 : 0,total.negative ? -1 : 0]) : totals.flatMap(total => [total.positive,-total.negative]);
  return {mode,totals,stacks,domainValues};
}

function regression(points) {
  const valid=points.filter(point=>finite(point.x)&&finite(point.y));
  if(valid.length<2) return null;
  const meanX=valid.reduce((sum,p)=>sum+p.x,0)/valid.length,meanY=valid.reduce((sum,p)=>sum+p.y,0)/valid.length;
  const denominator=valid.reduce((sum,p)=>sum+(p.x-meanX)**2,0);
  if (Math.abs(denominator)<=EPS) return {slope:0,intercept:meanY,r2:0};
  const slope=valid.reduce((sum,p)=>sum+(p.x-meanX)*(p.y-meanY),0)/denominator,intercept=meanY-slope*meanX;
  const ssTot=valid.reduce((sum,p)=>sum+(p.y-meanY)**2,0),ssRes=valid.reduce((sum,p)=>sum+(p.y-(slope*p.x+intercept))**2,0);
  return {slope,intercept,r2:ssTot<=EPS?1:1-ssRes/ssTot};
}

function quartile(values, p) {
  const sorted=values.slice().sort((a,b)=>a-b); if(!sorted.length)return null;
  const position=(sorted.length-1)*p,lo=Math.floor(position),hi=Math.ceil(position);
  return sorted[lo]+(sorted[hi]-sorted[lo])*(position-lo);
}

function boxGroups(model, plan) {
  const categoryIndex=fieldIndex(model,model.mapping?.category),valueIndex=fieldIndex(model,model.mapping?.value||model.mapping?.y),groups=new Map();
  (model.dataset?.rows||[]).forEach((row,index)=>{const value=row?.[valueIndex];if(!finite(value))return;const key=categoryIndex>=0?String(row?.[categoryIndex]??''): 'All';if(!groups.has(key))groups.set(key,[]);groups.get(key).push(value);});
  const labels=[...groups.keys()]; const values=labels.flatMap(label=>groups.get(label)); return {labels,groups,values};
}

function histogram(model) {
  const valueIndex=fieldIndex(model,model.mapping?.value||model.mapping?.y),values=numericValues((model.dataset?.rows||[]).map(row=>row?.[valueIndex]));
  if(!values.length)return {values,edges:[0,1],counts:[0]};
  const configuredBins=Number(model.visual?.bins); const bins=Number.isInteger(configuredBins)?clamp(configuredBins,3,40):Math.min(16,Math.max(6,Math.ceil(Math.sqrt(values.length))));
  const min=Math.min(...values),max=Math.max(...values),pad=min===max?Math.max(1,Math.abs(min)*.05):0,lo=min-pad,hi=max+pad,step=(hi-lo)/bins,edges=Array.from({length:bins+1},(_,i)=>lo+step*i),counts=Array(bins).fill(0);
  values.forEach(value=>counts[clamp(Math.floor((value-lo)/Math.max(EPS,step)),0,bins-1)]++); return {values,edges,counts};
}

function pareto(model) {
  const categoryIndex=fieldIndex(model,model.mapping?.category),valueIndex=fieldIndex(model,model.mapping?.value||model.mapping?.y),groups=new Map();
  (model.dataset?.rows||[]).forEach(row=>{const label=String(row?.[categoryIndex]??'');const value=row?.[valueIndex];if(!label||!finite(value))return;groups.set(label,(groups.get(label)||0)+value);});
  const entries=[...groups.entries()].sort((a,b)=>b[1]-a[1]||compareLabels(a[0],b[0])),total=entries.reduce((sum,item)=>sum+item[1],0),max=Math.max(...entries.map(item=>item[1]),0),running=[];let sum=0;entries.forEach(([,value])=>{sum+=value;running.push(total?sum/total:0);});return {entries,total,max,running};
}

function layoutFor(model, data, width, height) {
  const xLabels=data.labels.length?data.labels:data.xKeys.map(value=>String(value));
  const maxYLabel=Math.max(...[0,...(data.yTickLabels||[])].map(value=>approxTextWidth(value,10)));
  const maxXLabel=Math.max(...[0,...xLabels.map(value=>approxTextWidth(shortText(value,20),10))]);
  const horizontal=model.chart_type==='Horizontal Bar';
  const rotation=clamp(Number(model.axes?.x?.rotation)||0,-90,90),rad=Math.abs(rotation)*Math.PI/180;
  const xLabelSpace=horizontal?24:(rotation===0?Math.min(42,Math.max(18,maxXLabel*.34)):Math.min(110,Math.max(32,maxXLabel*Math.sin(rad)+28)));
  const titleSpace=model.axes?.x?.title?20:0, yTitleSpace=model.axes?.y?.title?24:0;
  const legendEntries=(model.legend?.show!==false?data.series.filter(series=>series.legend):[]);
  const legendPosition=['top','right','bottom','left'].includes(model.legend?.position)?model.legend.position:'bottom';
  const verticalLegend=legendPosition==='left'||legendPosition==='right'||model.legend?.orientation==='vertical';
  const legendItemWidth=legendEntries.map(series=>approxTextWidth(series.name,9)+28);
  const availableWidth=Math.max(120,width-160), rowsHorizontal=Math.max(1,Math.ceil(legendItemWidth.reduce((sum,item)=>sum+item,0)/availableWidth));
  const legendHeight=legendEntries.length?(verticalLegend?Math.min(legendEntries.length,Math.max(2,Math.floor((height-80)/18)))*18:Math.min(rowsHorizontal,Math.max(1,Math.floor((height-100)/18)))*18):0;
  const legendWidth=legendEntries.length&&verticalLegend?Math.min(150,Math.max(104,Math.max(...legendItemWidth,104))):0;
  const categoryLabelWidth=Math.min(160,Math.max(64,Math.ceil(maxXLabel)));
  const leftBase=horizontal?categoryLabelWidth+26:Math.max(52,Math.min(170,Math.ceil(maxYLabel)+yTitleSpace+12));
  const rightBase=horizontal?Math.max(30,Math.min(96,Math.ceil(maxYLabel/2)+24)):Math.max(28,model.axes?.y?.position==='right'?Math.min(90,Math.ceil(maxYLabel)+yTitleSpace):28);
  const left=leftBase+(legendPosition==='left'&&verticalLegend?legendWidth:0);
  const right=rightBase+(legendPosition==='right'&&verticalLegend?legendWidth:0);
  const top=38+(legendPosition==='top'?legendHeight:0), bottom=24+xLabelSpace+(horizontal&&model.axes?.y?.title?20:0)+(legendPosition==='bottom'?legendHeight:0);
  const plotWidth=Math.max(horizontal?64:80,width-left-right),plotHeight=Math.max(100,height-top-bottom);
  return {width,height,left,right,top,bottom,plotWidth,plotHeight,legendPosition,legendHeight,legendWidth,xLabelSpace,rotation,verticalLegend,horizontal,categoryLabelWidth};
}

function makeTicks(domain, count) {
  const wanted=clamp(Number.isInteger(count)?count:5,2,12); if(domain.max===domain.min)return [domain.min];
  const step=niceStep(domain.max-domain.min,wanted),start=Math.ceil(domain.min/step)*step,values=[];
  for(let value=start;value<=domain.max+step*.001&&values.length<20;value+=step) values.push(Number(value.toFixed(12)));
  if(!values.length||values[0]>domain.min+EPS) values.unshift(domain.min);
  if(values.at(-1)<domain.max-EPS) values.push(domain.max);
  return values.slice(0,wanted+1);
}

function visibleTickIndexes(count, wanted) {
  if(count<=wanted)return Array.from({length:count},(_,i)=>i);
  const indexes=[]; for(let i=0;i<wanted;i++) indexes.push(Math.round(i*(count-1)/Math.max(1,wanted-1))); return unique(indexes);
}

function buildLegend(plan, model, layout, theme) {
  const entries=plan.series.filter(series=>series.legend); if(model.legend?.show===false||!entries.length)return '';
  const pos=layout.legendPosition, vertical=layout.verticalLegend, boxX=pos==='right'?plan.width-layout.legendWidth+8:pos==='left'?8:layout.left, boxY=pos==='top'?12:pos==='bottom'?plan.height-layout.legendHeight+4:layout.top;
  const usable=vertical?layout.legendWidth-14:Math.max(140,plan.width-layout.left-layout.right), lineHeight=18, font=entries.length>10?9:10;
  let cursorX=boxX,cursorY=boxY,markup='';
  entries.forEach((series,index)=>{
    const itemWidth=Math.min(usable,Math.max(64,approxTextWidth(series.name,font)+28));
    if(index>0 && (vertical || cursorX+itemWidth>boxX+usable)){cursorX=boxX;cursorY+=lineHeight;}
    const label=shortText(series.name,vertical?24:28),full=esc(series.name);
    markup+=`<g class="cs-legend-item" data-legend-series="${full}" data-series-key="${esc(series.key)}" data-series-visible="${series.visible?'true':'false'}" tabindex="0" role="button" aria-pressed="${series.visible?'true':'false'}" aria-label="Toggle ${full} series" opacity="${series.visible?1:.42}"><rect x="${cursorX.toFixed(1)}" y="${(cursorY+2).toFixed(1)}" width="10" height="10" rx="2" fill="${series.color}"/><text x="${(cursorX+16).toFixed(1)}" y="${(cursorY+11).toFixed(1)}" font-size="${font}" fill="${theme.muted}"><title>${full}</title>${esc(label)}</text></g>`;
    cursorX+=itemWidth;
  });
  return `<g class="cs-legend" data-legend-position="${pos}" data-legend-orientation="${model.legend?.orientation||'horizontal'}" aria-label="Chart legend">${markup}</g>`;
}

function selectionColumns(model, {seriesKey=null, secondary=false}={}) {
  const mapping=model.mapping||{}, fields=model.dataset?.fields||[], ids=[];
  const add=id=>{if(id&&!ids.includes(id)){const index=fields.findIndex(item=>item.id===id);if(index>=0)ids.push(id);}};
  const type=model.chart_type;
  if(type==='Histogram'||type==='Box Plot') add(mapping.value||mapping.y);
  else if(type==='Pareto'||BAR_TYPES.has(type)) { add(mapping.category||mapping.x||mapping.time); add(mapping.value||mapping.y); }
  else { add(mapping.x||mapping.time||mapping.category); add(mapping.y||mapping.value); }
  add(mapping.series||mapping.color);
  if(secondary || (seriesKey && (model.series||[]).some(series => String(series.key??series.name??series.label??'')===String(seriesKey) && series.axis==='secondary'))) add(mapping.secondaryY);
  return ids.map(id=>fields.findIndex(item=>item.id===id)).filter(index=>index>=0);
}

function barGeometry(plan) {
  const {model,layout,data}=plan, horizontal=plan.type==='Horizontal Bar', count=Math.max(1,data.xKeys.length), visible=plan.series.filter(series=>series.visible), band=(horizontal?layout.plotHeight:layout.plotWidth)/count, mode=plan.stack?.mode||'grouped', slot=band*(model.visual?.barWidth||.62)/Math.max(1,mode==='grouped'?visible.length:1), marks=[];
  data.xKeys.forEach((key,index)=>visible.forEach((series,visibleIndex)=>{
    const originalIndex=plan.series.indexOf(series),stack=plan.stack?.stacks[originalIndex]?.[index],value=stack?.value ?? data.bySeries[originalIndex]?.[index]?.y;
    if(!finite(value))return;
    const display=stack?.display ?? value,base=stack?.base ?? 0,end=base+display;
    let x,y,w,h;
    if(horizontal){
      const xStart=plan.valueAt(base,'primary'),xEnd=plan.valueAt(end,'primary');
      y=layout.top+index*band+(band-slot)/2;x=Math.min(xStart,xEnd);w=Math.max(1,Math.abs(xStart-xEnd));h=slot;
    } else {
      const yStart=plan.yAt(base,'primary'),yEnd=plan.yAt(end,'primary');
      x=layout.left+index*band+(mode==='grouped'?visibleIndex*slot+(band-visible.length*slot)/2:(band-slot)/2);y=Math.min(yStart,yEnd);w=slot;h=Math.max(1,Math.abs(yStart-yEnd));
    }
    marks.push({x,y,w,h,base,end,display,value,series,key,index,sourceIndex:data.bySeries[originalIndex]?.[index]?.sourceIndex ?? index,orientation:horizontal?'horizontal':'vertical',selectionCols:selectionColumns(model,{seriesKey:series.key})});
  }));
  return marks;
}

function makePlan(model, {width=760,height=400}={}) {
  if(!CORE_TYPES.has(model.chart_type)) throw new Error(`Canonical renderer does not own ${model.chart_type}`);
  const raw=buildRows(model), data=prepareRows(model,raw), type=model.chart_type;
  const bar=BAR_TYPES.has(type), stack=bar?stackInfo(data,model):null, hist=type==='Histogram'?histogram(model):null, box=type==='Box Plot'?boxGroups(model,data):null, paretoData=type==='Pareto'?pareto(model):null;
  let yValues=[];
  if(bar && stack) yValues=stack.domainValues;
  else if(type==='Box Plot') yValues=box.values;
  else if(type==='Histogram') yValues=hist.counts;
  else if(type==='Pareto') yValues=paretoData.entries.map(item=>item[1]);
  else yValues=data.rows.map(row=>row.y);
  const zeroBaseline=Boolean(model.axes?.y?.zeroBaseline) && !['Scatter Plot','Regression Scatter','Histogram','Box Plot'].includes(type);
  const percentDomain=bar && stack?.mode==='percent';
  const yDomain=percentDomain?{min:stack.domainValues.some(value=>value<0)?-1:0,max:1}:extent(yValues,{min:model.axes?.y?.min,max:model.axes?.y?.max},{zeroBaseline,fallback:[0,1]});
  const secondaryValues=data.series.filter(series=>series.axis==='secondary').flatMap(series=>data.bySeries[data.series.indexOf(series)].map(point=>point.y));
  const secondaryDomain=extent(secondaryValues,{min:model.axes?.secondaryY?.min,max:model.axes?.secondaryY?.max},{zeroBaseline:false,fallback:[0,1]});
  const yTickLabels=makeTicks(yDomain,model.axes?.y?.tickCount).map(value=>axisFormat(model.axes.y,value,{percentDomain}));
  const xDomain=type==='Histogram'?{min:hist.edges[0],max:hist.edges.at(-1)}:data.xDomain,layout=layoutFor(model,{...data,yTickLabels},Number(width)||760,Number(height)||400),xTicks=type==='Histogram'?makeTicks(xDomain,model.axes?.x?.tickCount):raw.xNumeric?makeTicks(xDomain,model.axes?.x?.tickCount):visibleTickIndexes(data.xKeys.length,model.axes?.x?.tickCount);
  return {model,type,width:layout.width,height:layout.height,data:{...data,xDomain},stack,hist,box,paretoData,xDomain,yDomain,secondaryDomain,percentDomain,layout,xTicks,yTicks:makeTicks(yDomain,model.axes?.y?.tickCount),secondaryTicks:makeTicks(secondaryDomain,model.axes?.secondaryY?.tickCount||model.axes?.y?.tickCount),xField:raw.xField,temporal:type==='Histogram'?false:raw.temporal,xNumeric:type==='Histogram'?true:raw.xNumeric,series:data.series};
}

function renderTicks(plan, theme) {
  const {model,layout,data}=plan, axis=model.axes||{}, xAxis=axis.x||{}, yAxis=axis.y||{}, xBottom=xAxis.position!=='top', yRight=yAxis.position==='right', baseY=xBottom?layout.top+layout.plotHeight:layout.top, baseX=yRight?layout.left+layout.plotWidth:layout.left;
  const xAt=plan.xAt,yAt=plan.yAt, parts=[];
  if(plan.type==='Horizontal Bar') {
    const valueAxis=axis.y||{}, categoryAxis=axis.x||{}, valueBaseY=layout.top+layout.plotHeight;
    plan.yTicks.forEach(value=>{const x=plan.valueAt(value,'primary');if(valueAxis.grid!==false)parts.push(`<line class="cs-gridline cs-gridline-value" x1="${x}" y1="${layout.top}" x2="${x}" y2="${layout.top+layout.plotHeight}" stroke="${theme.grid}"/>`);parts.push(`<text class="cs-axis-label" x="${x}" y="${valueBaseY+16}" text-anchor="middle" fill="${theme.muted}">${esc(axisFormat(valueAxis,value,{percentDomain:plan.percentDomain}))}</text>`);});
    const categoryTicks=visibleTickIndexes(data.xKeys.length,categoryAxis.tickCount);
    categoryTicks.forEach(index=>{const y=layout.top+(index+.5)/Math.max(1,data.xKeys.length)*layout.plotHeight;if(categoryAxis.grid!==false)parts.push(`<line class="cs-gridline cs-gridline-category" x1="${layout.left}" y1="${y}" x2="${layout.left+layout.plotWidth}" y2="${y}" stroke="${theme.grid}" opacity=".35"/>`);const label=shortText(String(data.xKeys[index]??''),18);parts.push(`<text class="cs-axis-label" x="${layout.left-8}" y="${y+4}" text-anchor="end" fill="${theme.muted}" data-full-value="${esc(data.xKeys[index])}"><title>${esc(data.xKeys[index])}</title>${esc(label)}</text>`);});
    parts.push(`<line class="cs-axis-line" x1="${layout.left}" y1="${valueBaseY}" x2="${layout.left+layout.plotWidth}" y2="${valueBaseY}" stroke="${theme.ink}"/><line class="cs-axis-line" x1="${layout.left}" y1="${layout.top}" x2="${layout.left}" y2="${layout.top+layout.plotHeight}" stroke="${theme.ink}"/>`);
    if(yAxis.title)parts.push(`<text class="cs-axis-title" x="${layout.left+layout.plotWidth/2}" y="${layout.height-(model.legend?.show!==false?layout.legendHeight+4:8)}" text-anchor="middle" fill="${theme.ink}">${esc(yAxis.title)}</text>`);
    if(xAxis.title)parts.push(`<text class="cs-axis-title" transform="translate(16 ${layout.top+layout.plotHeight/2}) rotate(-90)" text-anchor="middle" fill="${theme.ink}">${esc(xAxis.title)}</text>`);
    return parts.join('');
  }
  if(yAxis.grid!==false) plan.yTicks.forEach(value=>{const y=yAt(value,'primary');parts.push(`<line class="cs-gridline" x1="${layout.left}" y1="${y}" x2="${layout.left+layout.plotWidth}" y2="${y}" stroke="${theme.grid}"/>`);});
  const hasSecondary=plan.series.some(series=>series.axis==='secondary')||plan.type==='Pareto';
  if(plan.secondaryDomain && hasSecondary) plan.secondaryTicks.forEach(value=>{const y=yAt(value,'secondary');parts.push(`<line class="cs-gridline cs-gridline-secondary" x1="${layout.left}" y1="${y}" x2="${layout.left+layout.plotWidth}" y2="${y}" stroke="${theme.grid}" opacity=".38"/>`);});
  const xTickLabels=plan.xTicks.map(tick=>plan.xNumeric?axisFormat(xAxis,tick,{temporal:plan.temporal}):xLabel(model,data.xKeys[tick],data.xKeys[tick],false));
  plan.xTicks.forEach((tick,index)=>{const x=plan.xNumeric?xAt(tick):xAt(tick,'category');if(xAxis.grid!==false)parts.push(`<line class="cs-gridline cs-gridline-x" x1="${x}" y1="${layout.top}" x2="${x}" y2="${layout.top+layout.plotHeight}" stroke="${theme.grid}" opacity=".55"/>`);const label=shortText(xTickLabels[index],20),anchor=layout.rotation>15?'end':layout.rotation<-15?'start':'middle',transform=layout.rotation?` transform="rotate(${layout.rotation} ${x} ${baseY+(xBottom?8:-8)})"`:'';const y=baseY+(xBottom?layout.xLabelSpace-8:-layout.xLabelSpace+15);parts.push(`<text class="cs-axis-label" x="${x}" y="${y}" text-anchor="${anchor}" fill="${theme.muted}"${transform} data-full-value="${esc(xTickLabels[index])}"><title>${esc(xTickLabels[index])}</title>${esc(label)}</text>`);});
  parts.push(`<line class="cs-axis-line" x1="${layout.left}" y1="${baseY}" x2="${layout.left+layout.plotWidth}" y2="${baseY}" stroke="${theme.ink}"/><line class="cs-axis-line" x1="${baseX}" y1="${layout.top}" x2="${baseX}" y2="${layout.top+layout.plotHeight}" stroke="${theme.ink}"/>`);
  plan.yTicks.forEach(value=>{const y=yAt(value,'primary'),label=axisFormat(yAxis,value,{percentDomain:plan.percentDomain}),x=yRight?baseX+8:baseX-8;parts.push(`<text class="cs-axis-label" x="${x}" y="${y+4}" text-anchor="${yRight?'start':'end'}" fill="${theme.muted}">${esc(label)}</text>`);});
  if(hasSecondary) plan.secondaryTicks.forEach(value=>{const y=yAt(value,'secondary'),label=axisFormat(plan.type==='Pareto'?{format:'percent'}:axis.secondaryY||{},value,{percentDomain:plan.type==='Pareto'}),x=layout.left+layout.plotWidth+8;parts.push(`<text class="cs-axis-label cs-axis-secondary" x="${x}" y="${y+4}" text-anchor="start" fill="${theme.muted}">${esc(label)}</text>`);});
  if(xAxis.title)parts.push(`<text class="cs-axis-title" x="${layout.left+layout.plotWidth/2}" y="${xBottom?layout.height-(model.legend?.show!==false?layout.legendHeight+4:8):layout.top-20}" text-anchor="middle" fill="${theme.ink}">${esc(xAxis.title)}</text>`);
  if(yAxis.title)parts.push(`<text class="cs-axis-title" transform="translate(${yRight?layout.width-12:16} ${layout.top+layout.plotHeight/2}) rotate(-90)" text-anchor="middle" fill="${theme.ink}">${esc(yAxis.title)}</text>`);
  if(hasSecondary && (axis.secondaryY?.title||plan.type==='Pareto'))parts.push(`<text class="cs-axis-title" transform="translate(${layout.width-2} ${layout.top+layout.plotHeight/2}) rotate(-90)" text-anchor="middle" fill="${theme.ink}">${esc(axis.secondaryY?.title||'Cumulative %')}</text>`);
  return parts.join('');
}

function pathFor(points, smooth=false) {
  if(!points.length)return '';
  if(!smooth)return points.map((point,index)=>`${index?'L':'M'}${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' ');
  let path=`M${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;
  for(let i=1;i<points.length;i++){const prev=points[i-1],next=points[i],cx=(prev.x+next.x)/2;path+=` C${cx.toFixed(2)} ${prev.y.toFixed(2)} ${cx.toFixed(2)} ${next.y.toFixed(2)} ${next.x.toFixed(2)} ${next.y.toFixed(2)}`;}
  return path;
}

function labelMarkup(plan, point, text, color, index) {
  const {layout,model}=plan, position=model.visual?.labelPosition||'top'; let y=point.y-7;
  if(position==='bottom')y=point.y+15; if(position==='center')y=point.y+4; if(position==='inside')y=point.y+4;
  y=clamp(y,layout.top+10,layout.top+layout.plotHeight-2);
  return `<text class="cs-value-label" data-label-index="${index}" x="${point.x.toFixed(2)}" y="${y.toFixed(2)}" text-anchor="middle" fill="${color}"><title>${esc(text)}</title>${esc(text)}</text>`;
}

function renderBar(plan, theme) {
  const {model}=plan,marks=[];
  barGeometry(plan).forEach(mark=>{const label=axisFormat(model.axes.y,mark.display,{percentDomain:plan.percentDomain}),full=`${mark.series.name} · ${String(mark.key)} · ${label}`;marks.push(`<rect class="cs-mark cs-bar-mark" data-chart-point="${mark.sourceIndex}" data-behavior-point="${mark.sourceIndex}" data-series-key="${esc(mark.series.key)}" data-selection-cols="${mark.selectionCols.join(',')}" data-bar-orientation="${mark.orientation}" data-bar-base="${mark.base}" data-bar-end="${mark.end}" data-bar-display="${mark.display}" data-tooltip="${esc(full)}" tabindex="0" role="button" aria-label="${esc(full)}" x="${mark.x.toFixed(2)}" y="${mark.y.toFixed(2)}" width="${mark.w.toFixed(2)}" height="${mark.h.toFixed(2)}" fill="${mark.series.color}" rx="2"><title>${esc(full)}</title></rect>`);if(model.visual?.dataLabels)marks.push(labelMarkup(plan,{x:mark.x+mark.w/2,y:mark.y+(mark.h>18?Math.min(18,mark.h/2):0)},label,theme.ink,mark.index));});
  return marks.join('');
}

function renderLineLike(plan, theme) {
  const {model,layout,data}=plan,parts=[]; const baseline=model.axes?.y?.zeroBaseline?0:plan.yDomain.min;
  plan.series.forEach((series,seriesIndex)=>{if(!series.visible)return;const sourcePoints=data.rows.filter(row=>row.series===series.key),points=sourcePoints.map(point=>{const categoryIndex=plan.xNumeric?point.xValue:data.xKeys.indexOf(String(point.xRaw??'')),x=plan.xAt(categoryIndex,plan.xNumeric?'numeric':'category'),y=finite(point.y)?plan.yAt(point.y,series.axis):null;return {...point,x,y};});let segment=[];const flush=()=>{if(!segment.length)return;const line=pathFor(segment,series.smoothing);if(plan.type==='Area Chart'){const first=segment[0],last=segment.at(-1),baseY=plan.yAt(baseline,series.axis);parts.push(`<path class="cs-area cs-series-${seriesIndex}" data-series-key="${esc(series.key)}" d="M${first.x.toFixed(2)} ${baseY.toFixed(2)} ${segment.map(point=>`L${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(' ')} L${last.x.toFixed(2)} ${baseY.toFixed(2)} Z" fill="${series.color}" fill-opacity="${model.visual?.areaOpacity ?? .25}"><title>${esc(series.name)} area</title></path>`);}parts.push(`<path class="cs-line cs-series-${seriesIndex}" data-series-key="${esc(series.key)}" d="${line}" fill="none" stroke="${series.color}" stroke-width="${series.lineWidth}" stroke-dasharray="${series.lineDash==='dashed'?'8 5':series.lineDash==='dotted'?'2 4':'none'}" stroke-linecap="round" stroke-linejoin="round"><title>${esc(series.name)}</title></path>`);segment=[];};
    points.forEach(point=>{if(point.y===null){flush();return;}segment.push(point);});flush();
    if(series.markers)points.filter(point=>point.y!==null).forEach((point,index)=>{const label=axisFormat(series.axis==='secondary'?model.axes.secondaryY:model.axes.y,point.y,{percentDomain:series.axis==='primary'&&plan.percentDomain}),full=`${series.name} · ${xLabel(model,point.xRaw,point.x,plan.temporal)} · ${label}`;parts.push(`<circle class="cs-mark cs-point-mark" data-chart-point="${point.sourceIndex ?? index}" data-behavior-point="${point.sourceIndex ?? index}" data-series-key="${esc(series.key)}" data-selection-cols="${selectionColumns(model,{seriesKey:series.key,secondary:point.secondary}).join(',')}" data-secondary="${point.secondary?'true':'false'}" data-tooltip="${esc(full)}" tabindex="0" role="button" aria-label="${esc(full)}" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="4" fill="${series.color}" stroke="${theme.bg}" stroke-width="2"><title>${esc(full)}</title></circle>`);if(model.visual?.dataLabels)parts.push(labelMarkup(plan,point,label,theme.ink,index));});
  });
  return parts.join('');
}

function renderScatter(plan, theme) {
  const {model,layout,data}=plan,points=data.rows.filter(row=>finite(row.xValue)&&finite(row.y)).map(row=>({x:plan.xAt(row.xValue,'numeric'),y:plan.yAt(row.y,'primary'),raw:row})),parts=[];
  const seriesByName=new Map(plan.series.map(series=>[series.key,series]));
  points.forEach((point,index)=>{const series=seriesByName.get(point.raw.series)||plan.series[0],yLabel=axisFormat(model.axes.y,point.raw.y),full=`${series?.name||point.raw.series} · ${point.raw.xRaw} · ${yLabel}`;parts.push(`<circle class="cs-mark cs-scatter-mark" data-chart-point="${point.raw.index}" data-behavior-point="${point.raw.index}" data-series-key="${esc(point.raw.series)}" data-selection-cols="${selectionColumns(model,{seriesKey:point.raw.series}).join(',')}" data-tooltip="${esc(full)}" tabindex="0" role="button" aria-label="${esc(full)}" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="5" fill="${series?.color||PALETTES.report[0]}" stroke="${theme.bg}" stroke-width="2"><title>${esc(full)}</title></circle>`);});
  if(plan.type==='Regression Scatter'){const fit=regression(data.rows.map(row=>({x:row.xValue,y:row.y})).filter(point=>finite(point.x)&&finite(point.y)));if(fit){const x1=plan.xDomain.min,x2=plan.xDomain.max,y1=fit.slope*x1+fit.intercept,y2=fit.slope*x2+fit.intercept;parts.push(`<path class="cs-regression-line" d="M${plan.xAt(x1,'numeric').toFixed(2)} ${plan.yAt(y1,'primary').toFixed(2)} L${plan.xAt(x2,'numeric').toFixed(2)} ${plan.yAt(y2,'primary').toFixed(2)}" fill="none" stroke="${PALETTES.report[4]}" stroke-width="2" stroke-dasharray="6 4"><title>Fitted trend · R² ${fit.r2.toFixed(3)}</title></path>`);}}
  return parts.join('');
}

function renderHistogram(plan, theme) {
  const {layout,model,hist}=plan,marks=[],zero=layout.top+layout.plotHeight,max=Math.max(...hist.counts,1),band=layout.plotWidth/Math.max(1,hist.counts.length);
  hist.counts.forEach((count,index)=>{const h=count/max*layout.plotHeight,x=layout.left+index*band+1,y=zero-h,label=`${axisFormat(model.axes.x,hist.edges[index])}–${axisFormat(model.axes.x,hist.edges[index+1])} · ${count}`;marks.push(`<rect class="cs-mark cs-histogram-bin" data-chart-point="${index}" data-behavior-point="${index}" data-selection-cols="${selectionColumns(model).join(',')}" data-tooltip="${esc(label)}" tabindex="0" role="img" aria-label="${esc(label)}" x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${Math.max(1,band-2).toFixed(2)}" height="${Math.max(1,h).toFixed(2)}" fill="${plan.series[0]?.color||PALETTES.report[0]}" fill-opacity=".78"><title>${esc(label)}</title></rect>`);}); return marks.join('');
}

function renderBox(plan, theme) {
  const {model,layout,box}=plan,parts=[],groups=box.labels.length?box.labels:['All'],band=layout.plotWidth/Math.max(1,groups.length),boxAxis={...model.axes.y,precision:Number.isInteger(model.axes.y.precision)?model.axes.y.precision:2};
  groups.forEach((label,index)=>{const values=box.groups.get(label)||[];if(!values.length)return;const minimum=Math.min(...values),maximum=Math.max(...values),q1=quartile(values,.25),median=quartile(values,.5),q3=quartile(values,.75),x=layout.left+band*(index+.5),color=plan.series[index%Math.max(1,plan.series.length)]?.color||PALETTES.report[index%PALETTES.report.length],top=plan.yAt(q3,'primary'),bottom=plan.yAt(q1,'primary'),full=`${label} · n=${values.length} · min ${axisFormat(boxAxis,minimum)} · median ${axisFormat(boxAxis,median)} · max ${axisFormat(boxAxis,maximum)}`;parts.push(`<g class="cs-box-group" data-chart-point="${index}" data-behavior-point="${index}" data-selection-cols="${selectionColumns(model).join(',')}" data-tooltip="${esc(full)}" tabindex="0" role="img" aria-label="${esc(full)}"><line x1="${x}" y1="${plan.yAt(minimum,'primary')}" x2="${x}" y2="${plan.yAt(maximum,'primary')}" stroke="${color}"/><line x1="${x-14}" y1="${plan.yAt(minimum,'primary')}" x2="${x+14}" y2="${plan.yAt(minimum,'primary')}" stroke="${color}"/><line x1="${x-14}" y1="${plan.yAt(maximum,'primary')}" x2="${x+14}" y2="${plan.yAt(maximum,'primary')}" stroke="${color}"/><rect x="${x-22}" y="${top}" width="44" height="${Math.max(1,bottom-top)}" fill="${color}" fill-opacity=".32" stroke="${color}" rx="3"/><line x1="${x-22}" y1="${plan.yAt(median,'primary')}" x2="${x+22}" y2="${plan.yAt(median,'primary')}" stroke="${theme.ink}" stroke-width="2"><title>${esc(full)}</title></line><text class="cs-axis-label" x="${x}" y="${layout.height-8}" text-anchor="middle" fill="${theme.muted}">${esc(shortText(label,16))}<title>${esc(label)}</title></text></g>`);}); return parts.join('');
}

function renderPareto(plan, theme) {
  const {layout,model,paretoData}=plan,count=paretoData.entries.length,band=layout.plotWidth/Math.max(1,count),barWidth=band*.7,parts=[];
  paretoData.entries.forEach(([label,value],index)=>{const x=layout.left+index*band+(band-barWidth)/2,y=plan.yAt(value,'primary'),h=layout.top+layout.plotHeight-y,series=plan.series[index%Math.max(1,plan.series.length)],full=`${label}: ${axisFormat(model.axes.y,value)} · cumulative ${axisFormat({format:'percent'},paretoData.running[index],{percentDomain:true})}`;parts.push(`<rect class="cs-mark cs-pareto-bar" data-chart-point="${index}" data-behavior-point="${index}" data-selection-cols="${selectionColumns(model).join(',')}" data-tooltip="${esc(full)}" tabindex="0" role="button" aria-label="${esc(full)}" x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${Math.max(1,h).toFixed(2)}" fill="${series?.color||PALETTES.report[index%PALETTES.report.length]}" rx="2"><title>${esc(full)}</title></rect><text class="cs-axis-label" x="${(x+barWidth/2).toFixed(2)}" y="${layout.height-8}" text-anchor="middle" fill="${theme.muted}" data-full-value="${esc(label)}"><title>${esc(label)}</title>${esc(shortText(label,14))}</text>`);});
  const line=paretoData.running.map((value,index)=>`${index?'L':'M'}${(layout.left+index*band+band/2).toFixed(2)} ${plan.yAt(value,'secondary').toFixed(2)}`).join(' ');parts.push(`<path class="cs-pareto-line" d="${line}" fill="none" stroke="${PALETTES.report[4]}" stroke-width="2.5"/><text class="cs-axis-title" x="${layout.width-layout.right}" y="${layout.top-12}" text-anchor="end" fill="${PALETTES.report[4]}">Cumulative %</text>`);return parts.join('');
}

function renderReferences(plan, theme) {
  const {model,layout}=plan, parts=[]; (model.reference_bands||[]).filter(band=>finite(band.low)&&finite(band.high)).forEach((band,index)=>{const y1=plan.yAt(band.high,'primary'),y2=plan.yAt(band.low,'primary'),top=Math.min(y1,y2),bottom=Math.max(y1,y2);parts.push(`<rect class="cs-reference-band" data-reference-id="${esc(band.id||index)}" x="${layout.left}" y="${top.toFixed(2)}" width="${layout.plotWidth}" height="${Math.max(1,bottom-top).toFixed(2)}" fill="${band.color||PALETTES.report[0]}" fill-opacity="${band.opacity??.12}"><title>${esc(band.label||'Reference band')} · ${axisFormat(model.axes.y,band.low)}–${axisFormat(model.axes.y,band.high)}</title></rect>`);if(band.label)parts.push(`<text class="cs-reference-label" x="${layout.left+5}" y="${clamp(top+12,layout.top+12,layout.top+layout.plotHeight-4)}" fill="${band.color||PALETTES.report[0]}">${esc(band.label)}</text>`);});
  (model.reference_lines||[]).filter(line=>finite(line.value)).forEach((line,index)=>{const y=plan.yAt(line.value,'primary'),label=`${line.label||'Reference'} ${axisFormat(model.axes.y,line.value,{percentDomain:plan.percentDomain})}`;parts.push(`<line class="cs-reference-line" data-reference-id="${esc(line.id||index)}" x1="${layout.left}" y1="${y.toFixed(2)}" x2="${layout.left+layout.plotWidth}" y2="${y.toFixed(2)}" stroke="${line.color||PALETTES.report[2]}" stroke-dasharray="${line.dash==='dotted'?'2 4':'6 4'}"/><text class="cs-reference-label" x="${layout.left+layout.plotWidth-4}" y="${clamp(y-5,layout.top+10,layout.top+layout.plotHeight-4)}" text-anchor="end" fill="${line.color||PALETTES.report[2]}"><title>${esc(label)}</title>${esc(label)}</text>`);});
  return parts.join('');
}

function renderAnnotations(plan, theme) {
  const {model,layout}=plan; return (model.annotations||[]).filter(annotation=>annotation&&annotation.text).map((annotation,index)=>{const x=layout.left+clamp(Number(annotation.x)||.5,0,1)*layout.plotWidth,y=layout.top+clamp(Number(annotation.y)||.5,0,1)*layout.plotHeight,label=String(annotation.text);return `<g class="cs-annotation" data-annotation-id="${esc(annotation.id||index)}" tabindex="0" role="note" aria-label="${esc(label)}"><line x1="${x}" y1="${y}" x2="${x}" y2="${Math.max(layout.top,y-18)}" stroke="${theme.ink}" stroke-dasharray="3 3"/><rect x="${clamp(x+5,layout.left,layout.width-layout.right-150)}" y="${clamp(y-32,layout.top,layout.top+layout.plotHeight-24)}" width="145" height="22" rx="4" fill="${theme.surface}" stroke="${theme.grid}"/><text x="${clamp(x+11,layout.left+6,layout.width-layout.right-144)}" y="${clamp(y-17,layout.top+14,layout.top+layout.plotHeight-9)}" fill="${theme.ink}"><title>${esc(label)}</title>${esc(shortText(label,22))}</text></g>`;}).join('');
}

export function buildCanonicalChartPlan(model, options={}) {
  const plan=makePlan(model,options);
  plan.xAt=(value,mode)=>{const domain=plan.data.xDomain;if(plan.xNumeric||mode==='numeric')return plan.layout.left+(Number(value)-domain.min)/Math.max(EPS,domain.max-domain.min)*plan.layout.plotWidth;return plan.layout.left+(Number(value)+.5)/Math.max(1,plan.data.xKeys.length)*plan.layout.plotWidth;};
  plan.yAt=(value,axis='primary')=>{const domain=axis==='secondary'?plan.secondaryDomain:plan.yDomain;return plan.layout.top+plan.layout.plotHeight-(Number(value)-domain.min)/Math.max(EPS,domain.max-domain.min)*plan.layout.plotHeight;};
  plan.valueAt=(value,axis='primary')=>{const domain=axis==='secondary'?plan.secondaryDomain:plan.yDomain;return plan.layout.left+(Number(value)-domain.min)/Math.max(EPS,domain.max-domain.min)*plan.layout.plotWidth;};
  return plan;
}

export function canonicalBarRectangles(model, options={}) {
  const plan=buildCanonicalChartPlan(model,options);
  if(!BAR_TYPES.has(plan.type)) return [];
  return barGeometry(plan).map(mark=>({orientation:mark.orientation,category:String(mark.key),series:String(mark.series.key),sourceIndex:mark.sourceIndex,base:mark.base,end:mark.end,display:mark.display,x:mark.x,y:mark.y,width:mark.w,height:mark.h,selectionCols:mark.selectionCols}));
}

export function renderCanonicalChartSvg(model, {width=760,height=400,dark=false}={}) {
  const plan=buildCanonicalChartPlan(model,{width,height}),theme=dark?{bg:'#172234',ink:'#eef4fb',muted:'#a9b7ca',grid:'#3a4b63',surface:'#233149'}:{bg:'#fff',ink:'#152338',muted:'#637187',grid:'#d8e0ea',surface:'#f7f9fc'};
  const title=model.title||model.chart_type,description=`${model.chart_type} rendered from ${plan.data.rows.length} typed rows using the canonical Visembler chart authority.`;
  let marks=''; if(BAR_TYPES.has(plan.type))marks=renderBar(plan,theme); else if(plan.type==='Scatter Plot'||plan.type==='Regression Scatter')marks=renderScatter(plan,theme); else if(plan.type==='Histogram')marks=renderHistogram(plan,theme); else if(plan.type==='Box Plot')marks=renderBox(plan,theme); else if(plan.type==='Pareto')marks=renderPareto(plan,theme); else marks=renderLineLike(plan,theme);
  const interaction=model.interaction||{};
  const interactionAttrs=`data-interaction-tooltip="${interaction.tooltip!==false}" data-interaction-crosshair="${interaction.crosshair===true}" data-interaction-zoom="${interaction.zoom!==false}" data-interaction-pan="${interaction.pan!==false}" data-interaction-brush="${interaction.brush===true}" data-interaction-range-selector="${interaction.rangeSelector===true}" data-interaction-legend-filter="${interaction.legendFilter!==false}"`;
  return `<svg class="cs-chart-svg" data-renderer-authority="visembler-canonical-chart-v2" data-chart-type="${esc(plan.type)}" ${interactionAttrs} viewBox="0 0 ${plan.width} ${plan.height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${esc(title)}" xmlns="http://www.w3.org/2000/svg"><title>${esc(title)}</title><desc>${esc(description)}</desc><rect class="cs-chart-background" width="${plan.width}" height="${plan.height}" fill="${theme.bg}"/><rect class="cs-plot-area" x="${plan.layout.left}" y="${plan.layout.top}" width="${plan.layout.plotWidth}" height="${plan.layout.plotHeight}" fill="${theme.bg}" stroke="${theme.grid}"/>${renderTicks(plan,theme)}${renderReferences(plan,theme)}${marks}${renderAnnotations(plan,theme)}${buildLegend(plan,model,plan.layout,theme)}<g class="cs-crosshair" data-crosshair-layer="true" visibility="hidden"><line x1="${plan.layout.left}" y1="${plan.layout.top}" x2="${plan.layout.left}" y2="${plan.layout.top+plan.layout.plotHeight}" stroke="${theme.ink}" stroke-dasharray="3 3"/></g></svg>`;
}

export const CANONICAL_CHART_RENDERER = Object.freeze({name:'Visembler canonical chart renderer',version:2,coreTypes:[...CORE_TYPES]});
