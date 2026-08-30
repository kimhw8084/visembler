import assert from 'node:assert/strict';
import { TimelineContractError, prepareTimeline } from '../core/timeline_semantics_engine.mjs';

const dated = prepareTimeline('dated', {
  tasks: [
    { id:'spec', label:'Schema', start:'2026-08-18', end:'2026-08-20' },
    { id:'data', label:'Data', start:'2026-08-22', durationDays:3 },
    { id:'pilot', label:'Pilot', start:'2026-08-27', end:'2026-08-27', milestone:true },
  ],
  dependencies: [
    { source:'spec', target:'data', type:'FS', lagDays:1 },
    { source:'data', target:'pilot', type:'FS', lagDays:2 },
  ],
});
assert.equal(dated.tasks.find(t=>t.id==='data').end,'2026-08-25');
assert.equal(dated.tasks.find(t=>t.id==='data').dateProvenance.end,'derived_from_duration');
assert.deepEqual(dated.topologicalOrder,['spec','data','pilot']);
assert.equal(dated.fingerprint, prepareTimeline('dated', {
  tasks:[{id:'pilot',start:'2026-08-27',end:'2026-08-27',milestone:true,label:'Pilot'},{id:'data',start:'2026-08-22',durationDays:3,label:'Data'},{id:'spec',start:'2026-08-18',end:'2026-08-20',label:'Schema'}],
  dependencies:[{source:'data',target:'pilot',type:'FS',lagDays:2},{source:'spec',target:'data',type:'FS',lagDays:1}],
}).fingerprint);

const sequence = prepareTimeline('sequence', {
  tasks:[{id:'collect'},{id:'reason'},{id:'verify'}],
  dependencies:[{source:'collect',target:'reason'},{source:'reason',target:'verify'}],
});
assert.equal(sequence.dateSemantics,'none');
assert.ok(sequence.tasks.every(t=>!('start' in t)&&!('end' in t)&&!('durationDays' in t)));
assert.ok(sequence.dependencies.every(d=>d.type==='sequence'&&d.lagDays===0));

assert.throws(()=>prepareTimeline('dated',{tasks:[{id:'x',start:'2026-02-30',end:'2026-03-01'}]}),(e)=>e instanceof TimelineContractError&&e.code==='TIMELINE_DATE');
assert.throws(()=>prepareTimeline('dated',{tasks:[{id:'x',start:'2026-08-20',end:'2026-08-18'}]}),(e)=>e.code==='TIMELINE_RANGE');
assert.throws(()=>prepareTimeline('dated',{tasks:[{id:'x',start:'2026-08-18',end:'2026-08-20',durationDays:3}]}),(e)=>e.code==='TIMELINE_DURATION_MISMATCH');
assert.throws(()=>prepareTimeline('sequence',{tasks:[{id:'x',start:'2026-08-18'}]}),(e)=>e.code==='TIMELINE_SEQUENCE_DATE');
assert.throws(()=>prepareTimeline('dated',{
  tasks:[{id:'a',start:'2026-08-18',end:'2026-08-20'},{id:'b',start:'2026-08-20',end:'2026-08-22'}],
  dependencies:[{source:'a',target:'b',type:'FS',lagDays:1}],
}),(e)=>e.code==='TIMELINE_DEPENDENCY_VIOLATION');
assert.throws(()=>prepareTimeline('dated',{
  tasks:[{id:'a',start:'2026-08-18',end:'2026-08-20'},{id:'b',start:'2026-08-22',end:'2026-08-24'}],
  dependencies:[{source:'a',target:'b'},{source:'b',target:'a'}],
}),(e)=>e.code==='TIMELINE_DEPENDENCY_CYCLE');

console.log(JSON.stringify({pass:true,modes:2,dependencyTypes:4,noInventedDates:true,deterministic:true,invalidScheduleBlocking:true,fingerprint:dated.fingerprint},null,2));
