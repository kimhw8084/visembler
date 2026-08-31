import { intakeText } from './authoring_data.mjs';

self.onmessage=({data})=>{
  try { self.postMessage({id:data.id,result:intakeText(data.text)}); }
  catch(error) { self.postMessage({id:data.id,error:String(error?.message||error)}); }
};
