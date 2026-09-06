// One bounded worker request. Superseded/failed work is terminated, all handlers
// and timers are released, and a subsequent parse always gets a usable worker.
export function createIntakeClient({makeWorker,parseInline,threshold=250000,timeoutMs=15000,setTimer=setTimeout,clearTimer=clearTimeout}) {
  let pending=null,sequence=0;
  const cancel=(reason='Parsing cancelled')=>{if(pending)pending.finish(new Error(reason));};
  function parse(value) {
    const text=String(value||'');cancel('Parsing superseded');
    if(text.length<threshold)return Promise.resolve().then(()=>parseInline(text));
    return new Promise((resolve,reject)=>{
      let worker,timer,done=false;
      const job={finish(error,result){
        if(done)return;done=true;clearTimer(timer);
        if(worker){worker.onmessage=null;worker.onerror=null;worker.onmessageerror=null;worker.terminate();}
        if(pending===job)pending=null;
        error?reject(error):resolve(result);
      }};
      pending=job;
      try {
        worker=makeWorker();const id=++sequence;
        worker.onmessage=event=>{if(event.data?.id!==id)return;event.data.error?job.finish(new Error(event.data.error)):job.finish(null,event.data.result?.rows?.length?event.data.result:null);};
        worker.onerror=event=>{event.preventDefault?.();job.finish(new Error('Data parser failed. Paste again to retry.'));};
        worker.onmessageerror=()=>job.finish(new Error('Data parser returned an unreadable result.'));
        timer=setTimer(()=>job.finish(new Error('Data parsing timed out. Try a smaller export.')),timeoutMs);
        worker.postMessage({id,text});
      } catch(error){job.finish(error);}
    });
  }
  return {parse,cancel,get pendingCount(){return pending?1:0;}};
}
