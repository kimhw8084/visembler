import assert from 'node:assert/strict';
import { compileGridLayout, findLargestEmptyRegion, mapPlacementToRegion } from '../core/grid_layout_engine.mjs';
const page={width:13.333,height:7.5};const obstacles=[{x:.3,y:.18,width:12.73,height:.72},{x:.3,y:7.02,width:12.73,height:.28}];const target=findLargestEmptyRegion(page,obstacles,{padding:.06});
assert.ok(target.y>=.95&&target.y+target.height<=7.0);
const items=[{id:'a',col:0,row:0,colSpan:7,rowSpan:2},{id:'b',col:7,row:0,colSpan:5,rowSpan:2},{id:'c',col:0,row:2,colSpan:12,rowSpan:4}];
const a=compileGridLayout({page,targetRegion:target,columns:12,rows:6,gap:.08,items});const b=compileGridLayout({page,targetRegion:target,columns:12,rows:6,gap:.08,items});assert.equal(a.fingerprint,b.fingerprint);assert.equal(a.placements.length,3);
for(const p of a.placements){assert.ok(p.x>=target.x-1e-9&&p.y>=target.y-1e-9&&p.x+p.width<=target.x+target.width+1e-9&&p.y+p.height<=target.y+target.height+1e-9);const r=mapPlacementToRegion(p,{x:1,y:2,width:8,height:4});assert.ok(r.x>=1&&r.y>=2&&r.x+r.width<=9+1e-9&&r.y+r.height<=6+1e-9)}
let fuzz=0;for(let i=0;i<2500;i++){const w=4+(i%113)/10,h=3+((i*7)%69)/10,cols=1+(i%24),rows=1+((i*5)%16);const target={x:.1,y:.1,width:w-.2,height:h-.2};const plan=compileGridLayout({page:{width:w,height:h},targetRegion:target,columns:cols,rows,gap:.01,items:[{id:'x',col:0,row:0,colSpan:cols,rowSpan:rows}]});const p=plan.placements[0];assert.ok(Math.abs(p.width-target.width)<1e-6&&Math.abs(p.height-target.height)<1e-6);fuzz++;}
console.log(JSON.stringify({pass:true,deterministic:true,arbitraryPages:2500,safeMiddleRegion:target,normalizedMapping:true},null,2));
