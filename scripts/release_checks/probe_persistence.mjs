#!/usr/bin/env node
/** Read-only isolated-source probes, not a browser/release verifier.
 * node probe_persistence.mjs --repo /path/to/visembler --output results.json
 * node probe_persistence.mjs --reviewed-excerpts --output results.json
 * Explicit test doubles isolate journal/dispatch logic from NiceGUI/EditorStore.
 * Exit: 0 pass, 1 failed requirement, 2 setup/harness error.
 */
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';

const directory=path.dirname(fileURLToPath(import.meta.url));
const baseline='26e4fc0dde87d7ebee54ce1734e31abc11a198d1';
const args=process.argv.slice(2);let repo=null,output=null,reviewed=false;
for(let i=0;i<args.length;i++) {
  if(args[i]==='--repo')repo=args[++i];
  else if(args[i]==='--output')output=args[++i];
  else if(args[i]==='--reviewed-excerpts')reviewed=true;
  else throw new Error(`Unknown argument ${args[i]}`);
}
if(Boolean(repo)===reviewed) {
  console.error('Use exactly one of --repo PATH or --reviewed-excerpts');process.exit(2);
}
let head=baseline,dirty=null;
if(repo) {
  repo=path.resolve(repo);
  try { head=execFileSync('git',['-C',repo,'rev-parse','HEAD'],{encoding:'utf8'}).trim();
  dirty=execFileSync('git',['-C',repo,'status','--porcelain'],{encoding:'utf8'}).trim(); } catch { head=null;dirty='archive: no Git metadata'; }
}
if(reviewed)throw new Error('This delivery probe requires --repo; copied excerpts are not accepted.');
const source=fs.readFileSync(repo?path.join(repo,'company_ui/products/visualizer/assets/integrated_editor.mjs'):path.join(directory,'reviewed_excerpt.mjs'),'utf8');
function extract(name) {
  const re=new RegExp(`(?:^|\\n)((?:async\\s+)?function\\s+${name}\\s*\\()`);
  const match=re.exec(source);if(!match)throw new Error(`Missing function ${name}; update probe after refactor, do not weaken product.`);
  const start=match.index+match[0].indexOf(match[1]);
  for(let end=source.indexOf('}',start);end!==-1;end=source.indexOf('}',end+1)) {
    const text=source.slice(start,end+1);
    try{new vm.Script(`(${text})`);return text;}catch(e){if(!(e instanceof SyntaxError))throw e;}
  }
  throw new Error(`Cannot parse ${name}`);
}
function extractBridge() {
  const start=source.indexOf('window.CompanyUIVisualizerBridge=');
  if(start<0)throw new Error('Bridge assignment missing; update probe after refactor.');
  for(let end=source.indexOf(';',start);end!==-1;end=source.indexOf(';',end+1)) {
    const text=source.slice(start,end+1);
    try{new vm.Script(text);return text;}catch(e){if(!(e instanceof SyntaxError))throw e;}
  }
  throw new Error('Cannot parse bridge assignment');
}
function context(values={}){return vm.createContext({structuredClone,Map,Set,JSON,Date,console,...values});}
function install(ctx,names){for(const name of names)vm.runInContext(`${extract(name)};`,ctx,{timeout:1000});}
const clone=x=>JSON.parse(JSON.stringify(x));
const fixture=value=>({items:[{id:'c1',type:'metric',order:0,value}],datasets:[],groups:{}});
const noop=()=>{};
const results=[];
function check(id,title,fn) {
  const observed={};
  try{fn(observed);results.push({id,title,status:'PASS',observed});}
  catch(e){results.push({id,title,status:e.code==='ERR_ASSERTION'?'FAIL':'ERROR',observed,message:e.message});}
}
function redoCase() {
  let current=fixture(10),accepted;
  const forward=[{op:'item.patch',id:'c1',patch:{value:99}}];
  const inverse=[{op:'item.patch',id:'c1',patch:{value:10}}];
  const store={revision:3,canRedo:true,serialize:()=>JSON.stringify(current),redo(){current=fixture(99);this.revision++;return {inverse:{ops:inverse},redo:{ops:forward}};}};
  const ctx=context({store,ui:{previewPatches:new Map()},toast:noop,cancelPointerSession:noop,invalidateResolvedData:noop,pruneSelection:noop,clearTransientInteractionVisuals:noop,localCommitId:()=> 'redo-4',syncAccepted:a=>{accepted=clone(a);},renderAll:noop});
  install(ctx,['redo']);ctx.redo();return {current,accepted,forward};
}
check('CONTROL-REDO','Immediate redo model reflects the forward operation',o=>{
  const c=redoCase();o.displayModel=c.current.items[0].value;o.recordedAfter=JSON.parse(c.accepted.canonical_after).items[0].value;
  assert.equal(o.displayModel,99);assert.equal(o.recordedAfter,99);
});
check('PERSIST-REDO','Replaying queued redo operations produces canonical_after',o=>{
  const c=redoCase();const replay=JSON.parse(c.accepted.canonical_before);
  for(const op of c.accepted.payload.ops){assert.equal(op.op,'item.patch');Object.assign(replay.items.find(x=>x.id===op.id),op.patch);}
  o.canonicalAfter=JSON.parse(c.accepted.canonical_after).items[0].value;o.replayedValue=replay.items[0].value;o.queuedOps=c.accepted.payload.ops;
  assert.equal(JSON.stringify(replay),c.accepted.canonical_after,'Redo recovery records inverse operations rather than the forward redo operations.');
});
function recoveryContext(failStorage=false) {
  const memory=new Map(),notifications=[];
  const pending={commit_id:'edit-2',report_id:'A',base_revision:1,model:fixture(99),ops:[{op:'item.patch',id:'c1',patch:{value:99}}],canonical_before:JSON.stringify(fixture(10))};
  const ui={pendingCommits:new Map([['edit-2',pending]]),recovery:null,saveInFlight:'edit-2',persistenceFailure:null};
  const storage={get:k=>memory.get(k)??null,set(k,v){if(failStorage)return false;memory.set(k,v);return true;},remove:k=>memory.delete(k)};
  const ctx=context({ui,storage,bootstrap:{report_id:'A'},store:{serialize:()=>JSON.stringify(fixture(99))},parseCanonical:x=>typeof x==='string'?JSON.parse(x):clone(x),toast:m=>notifications.push(m),debugEvent:noop,updateSaveUi:noop});
  install(ctx,['persistenceKey','sameValue','persistPendingState','retainLocalRecovery','restorePersistedRecovery']);
  return {ctx,ui,memory,notifications};
}
check('CONTROL-PENDING','Existing pending journal is restored on reload',o=>{
  const c=recoveryContext();c.ctx.persistPendingState();c.ui.pendingCommits.clear();c.ctx.restorePersistedRecovery({report_id:'A',model:fixture(10)});
  o.recovered=Boolean(c.ui.recovery);assert.equal(o.recovered,true);
});
check('PERSIST-RECOVERY','Recovery-only draft survives persist then reload',o=>{
  const c=recoveryContext();c.ctx.retainLocalRecovery('Conflict');const saved=JSON.parse(c.memory.get('viz-pending-report:A'));
  o.savedPending=saved.pending.length;o.savedRecoveryOps=saved.recovery.pending.length;
  c.ui.pendingCommits.clear();c.ui.recovery=null;c.ctx.restorePersistedRecovery({report_id:'A',model:fixture(10)});
  o.recovered=Boolean(c.ui.recovery);assert.equal(o.recovered,true,'Saved recovery.pending is ignored when saved.pending is empty.');
});
check('PERSIST-STORAGE','Failed local recovery storage produces a visible failure signal',o=>{
  const c=recoveryContext(true);c.ctx.persistPendingState();o.localWrites=c.memory.size;o.notifications=c.notifications;o.persistenceFailure=c.ui.persistenceFailure;
  assert.ok(c.ui.persistenceFailure||c.notifications.length,'storage.set returned false, but no failure state or warning was produced.');
});
function bridgeCase(type,reportId) {
  const calls=[],ui={pendingCommits:new Map([['B-save',{report_id:'B'}]]),saveInFlight:'B-save',recovery:null,persistenceFailure:null};
  const ctx=context({window:{},BRIDGE_VERSION:1,bootstrap:{report_id:'B'},ui,debugEvent:noop,replaceFromServer:p=>calls.push(clone(p)),persistPendingState:noop,updateSaveUi:noop,dispatchNextPendingCommit:noop,toast:noop});
  vm.runInContext(extractBridge(),ctx,{timeout:1000});
  const payload=type==='report.error'?{commit_id:`${reportId}-save`,message:'rejected',report:{report_id:reportId,revision:2,model:fixture(10)}}:{report_id:reportId,revision:2,rejected_commit_id:`${reportId}-save`,model:fixture(10)};
  ctx.window.CompanyUIVisualizerBridge.receive({bridge_version:1,type,payload});return {calls,ui};
}
check('CONTROL-CONFLICT','Current-report conflict is routed for recovery',o=>{
  const c=bridgeCase('report.conflict','B');o.replacements=c.calls.map(x=>x.report_id);assert.equal(c.calls.length,1);assert.equal(c.calls[0].report_id,'B');
});
check('PERSIST-LATE-CONFLICT','Late conflict from report A cannot replace active B',o=>{
  const c=bridgeCase('report.conflict','A');o.replacements=c.calls.map(x=>x.report_id);o.inflight=c.ui.saveInFlight;
  assert.equal(c.calls.length,0,'Stale A conflict is passed to replaceFromServer while B is active.');assert.equal(c.ui.saveInFlight,'B-save');
});
check('PERSIST-LATE-ERROR','Late error from report A cannot replace active B',o=>{
  const c=bridgeCase('report.error','A');o.replacements=c.calls.map(x=>x.report_id);o.persistenceFailure=c.ui.persistenceFailure;
  assert.equal(c.calls.length,0,'Stale A error with a report payload is passed to replaceFromServer while B is active.');assert.equal(c.ui.persistenceFailure,null);
});
const report={source_sha256:createHash('sha256').update(source).digest('hex'),baseline,checked_head:head,dirty,mode:repo?'actual-checkout-isolated-functions':'reviewed-excerpts-isolated-functions',scope:'Journal and bridge dispatch source functions. Explicit EditorStore, DOM, storage and transport test doubles; not full browser or persistence acceptance.',counts:Object.fromEntries(['PASS','FAIL','ERROR'].map(s=>[s,results.filter(x=>x.status===s).length])),results};
const encoded=JSON.stringify(report,null,2)+'\n';if(output){fs.mkdirSync(path.dirname(path.resolve(output)),{recursive:true});fs.writeFileSync(output,encoded);}console.log(encoded);process.exitCode=report.counts.ERROR?2:report.counts.FAIL?1:0;
