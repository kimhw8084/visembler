// Bounded, dependency-free safeguards for datasets that remain in the report model.
export const PERFORMANCE_LIMITS=Object.freeze({profileRows:20000,largeRows:10000,chartRows:1200,tableRows:500,engineeringRows:2400,waferRows:5000,diagramEdges:800});

export function sampledRows(rows, limit) {
  if(!Array.isArray(rows)||rows.length<=limit)return rows||[];
  if(limit<2)return rows.slice(0,limit);
  const result=[rows[0]],step=(rows.length-1)/(limit-1);
  for(let index=1;index<limit-1;index+=1)result.push(rows[Math.round(index*step)]);
  result.push(rows[rows.length-1]); return result;
}

export function performanceNotice(rowCount, displayed, noun='rows') {
  return rowCount>displayed?`${displayed.toLocaleString()} of ${rowCount.toLocaleString()} ${noun} shown for responsive authoring.`:'';
}
