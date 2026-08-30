import assert from 'node:assert/strict';
import fs from 'node:fs';
import { buildPivot, cellValue } from '../core/table_pivot_engine.mjs';

const F = JSON.parse(fs.readFileSync(new URL('./fixtures/pivot_reference.json', import.meta.url), 'utf8'));
const model = buildPivot(F.rows, {
  rows: ['site','tool'], columns: ['quarter','product'],
  measures: [
    {id:'rev_sum',field:'amount',aggregator:'sum'},
    {id:'def_avg',field:'defects',aggregator:'avg'},
    {id:'lot_distinct',field:'lot',aggregator:'distinct_count'},
    {id:'n',field:'amount',aggregator:'count'},
  ],
});
const samePath=(a,b)=>a.length===b.length&&a.every((v,i)=>Object.is(v,b[i]));
const rowByPath=(path)=>Object.values(model.rowsById).find((n)=>samePath(n.path,path));
const colByPath=(path)=>Object.values(model.columnsById).find((n)=>samePath(n.path,path));
let checked=0;
for(const e of F.expected){
  const r=rowByPath(e.row_path), c=colByPath(e.column_path);
  assert.ok(r,`missing row ${JSON.stringify(e.row_path)}`); assert.ok(c,`missing col ${JSON.stringify(e.column_path)}`);
  assert.equal(cellValue(model,r.id,c.id,'rev_sum'),e.rev_sum);
  assert.ok(Math.abs(cellValue(model,r.id,c.id,'def_avg')-e.def_avg)<1e-12);
  assert.equal(cellValue(model,r.id,c.id,'lot_distinct'),e.lot_distinct);
  assert.equal(cellValue(model,r.id,c.id,'n'),e.n);
  checked++;
}
console.log(JSON.stringify({pass:true,oracle:F.reference,seed:F.seed,sourceRows:F.rows.length,checkedCells:checked},null,2));
