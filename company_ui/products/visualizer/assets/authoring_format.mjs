// Presentation-only authoring helpers.
// These helpers never mutate canonical stored values.

export function formatMetricDisplay(value, {
  style='auto',
  decimals=null,
  currency='$',
}={}) {
  if(value===null||value===undefined||value==='') return null;
  if(style==='auto' || typeof value!=='number' || !Number.isFinite(value)) return String(value);

  const places=Number.isInteger(Number(decimals))
    ? Math.max(0,Math.min(6,Number(decimals)))
    : 1;

  if(style==='compact') {
    return new Intl.NumberFormat('en-US',{
      notation:'compact',
      maximumFractionDigits:places,
      minimumFractionDigits:0,
    }).format(value);
  }

  const formatted=new Intl.NumberFormat('en-US',{
    maximumFractionDigits:places,
    minimumFractionDigits:places,
    useGrouping:true,
  }).format(value);

  if(style==='currency') return `${currency||'$'}${formatted}`;
  return formatted;
}

export function metricDisplayUnit(entry={}) {
  if(entry.value_format==='percent') return '%';
  if(entry.value_format==='currency') return '';
  return String(entry.unit??'');
}

export function prepareChartRows(rawRows, {
  sortMode='input',
  missingPolicy='gap',
}={}) {
  let rows=(rawRows||[]).map((row,index)=>({
    ...row,
    __index:index,
    value:(missingPolicy==='zero' && (row?.value===null||row?.value===undefined||row?.value===''))
      ? 0
      : row?.value,
  }));

  if(missingPolicy==='drop') {
    rows=rows.filter(row=>row.value!==null&&row.value!==undefined&&row.value!=='');
  }

  const numeric=row=>typeof row.value==='number'&&Number.isFinite(row.value);

  if(sortMode==='value-asc' || sortMode==='value-desc') {
    const direction=sortMode==='value-asc'?1:-1;
    rows.sort((a,b)=>{
      const an=numeric(a),bn=numeric(b);
      if(an&&bn) return (a.value-b.value)*direction || a.__index-b.__index;
      if(an!==bn) return an?-1:1;
      return a.__index-b.__index;
    });
  } else if(sortMode==='label-asc') {
    rows.sort((a,b)=>String(a.label??'').localeCompare(String(b.label??''),undefined,{numeric:true})||a.__index-b.__index);
  }

  return rows.map(({__index,...row})=>row);
}
