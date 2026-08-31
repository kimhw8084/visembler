const clamp=(value,low,high)=>Math.min(high,Math.max(low,value));

export function chooseSnap(value, targets, threshold=8) {
  return targets.map((target,index)=>typeof target==='number'?{value:target,priority:9,index}:{...target,index})
    .filter(target=>Math.abs(target.value-value)<=threshold)
    .sort((a,b)=>Math.abs(a.value-value)-Math.abs(b.value-value)||a.priority-b.priority||a.index-b.index)[0]||null;
}

export function clampMovementDelta(rects, dx, dy, canvas, inset=0) {
  const left=Math.min(...rects.map(rect=>rect.x)), top=Math.min(...rects.map(rect=>rect.y));
  const right=Math.max(...rects.map(rect=>rect.x+rect.w)), bottom=Math.max(...rects.map(rect=>rect.y+rect.h));
  return {dx:clamp(dx,inset-left,canvas.w-inset-right),dy:clamp(dy,inset-top,canvas.h-inset-bottom)};
}

export function distributeRects(rects, axis, minimumGap=0) {
  const start = axis === 'x' ? 'x' : 'y';
  const size = axis === 'x' ? 'w' : 'h';
  const ordered = [...rects].sort((a, b) => a[start] - b[start] || String(a.id).localeCompare(String(b.id)));
  if (ordered.length < 3) return null;
  const first = ordered[0], last = ordered.at(-1);
  const span = last[start] + last[size] - first[start];
  const gap = (span - ordered.reduce((sum, rect) => sum + rect[size], 0)) / (ordered.length - 1);
  if (gap < minimumGap) return null;
  let position = first[start];
  return ordered.map((rect) => {
    const result = { id: rect.id, [start]: position };
    position += rect[size] + gap;
    return result;
  });
}

export function resizeRect(start, handle, delta, {minW,minH,canvas,inset=0,shift=false,alt=false}={}) {
  const west=handle.includes('w'), east=handle.includes('e'), north=handle.includes('n'), south=handle.includes('s');
  let left=start.x, right=start.x+start.w, top=start.y, bottom=start.y+start.h;
  if(west) left+=delta.x; if(east) right+=delta.x; if(north) top+=delta.y; if(south) bottom+=delta.y;
  if(alt){if(west)right-=delta.x;if(east)left-=delta.x;if(north)bottom-=delta.y;if(south)top-=delta.y;}
  if(right-left<minW){if(west)left=right-minW;else right=left+minW;}
  if(bottom-top<minH){if(north)top=bottom-minH;else bottom=top+minH;}
  if(shift){const ratio=start.w/start.h;let width=right-left,height=bottom-top;if((east||west)&&!(north||south))height=width/ratio;else if((north||south)&&!(east||west))width=height*ratio;else if(Math.abs(width-start.w)>=Math.abs(height-start.h)*ratio)height=width/ratio;else width=height*ratio;if(north)top=bottom-height;else if(!south){top=start.y+(start.h-height)/2;bottom=top+height;}else bottom=top+height;if(west)left=right-width;else if(!east){left=start.x+(start.w-width)/2;right=left+width;}else right=left+width;}
  left=clamp(left,inset,canvas.w-inset-minW); top=clamp(top,inset,canvas.h-inset-minH); right=clamp(right,left+minW,canvas.w-inset); bottom=clamp(bottom,top+minH,canvas.h-inset);
  return {x:left,y:top,w:right-left,h:bottom-top};
}

// Keyboard resize uses the same bounded, minimum-size-aware primitive as pointer
// resize.  Direction names intentionally describe the edge being moved.
export function resizeRectByKeyboard(start, direction, step, options={}) {
  const amount=Number.isFinite(Number(step))?Number(step):0;
  const handle={ArrowLeft:'w',ArrowRight:'e',ArrowUp:'n',ArrowDown:'s'}[direction];
  if(!handle) return {...start};
  const delta={x:0,y:0};
  if(direction==='ArrowLeft') delta.x=-amount;
  if(direction==='ArrowRight') delta.x=amount;
  if(direction==='ArrowUp') delta.y=-amount;
  if(direction==='ArrowDown') delta.y=amount;
  return resizeRect(start,handle,delta,options);
}
