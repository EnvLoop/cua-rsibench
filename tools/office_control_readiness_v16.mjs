/* Exact current control only, read-only readiness with indexed evidence. */
import {sameOfficeLoadingURL} from './office_loading_url_v15.mjs';
const check=(ok,code)=>{if(!ok)throw new Error(code);};
export async function waitCurrentControlReady({tab,expectedURL,node,retain,maximumMs=10000,requireEnabled=true,hidden=false,allowOfficeHints=false,clock=Date.now,observeIntervalMs=900,pause=ms=>new Promise(resolve=>setTimeout(resolve,ms))}){
 const began=clock(),cap=Math.ceil(maximumMs/observeIntervalMs)+1;
 const current=async()=>{check(clock()-began<maximumMs,'current_control_readiness_deadline');const actual=await tab.url();check(allowOfficeHints?sameOfficeLoadingURL(actual,expectedURL):actual===expectedURL,'current_control_readiness_URL_changed');};
 for(let i=0;i<cap;i++){
  await current();await retain(await tab.playwright.domSnapshot(),i);await current();const count=await node.count();check(count<=1,'current_control_readiness_ambiguous');
  const ready=hidden?(count===0||!await node.isVisible()):(count===1&&await node.isVisible()&&(!requireEnabled||await node.isEnabled()));
  if(ready){await current();return {readonly:true,observations:i+1,elapsed_ms:clock()-began,maximum_ms:maximumMs,hidden,exact_current_control_ready:true};}
  if(i+1<cap)await pause(Math.min(observeIntervalMs,Math.max(0,maximumMs-(clock()-began))));
 }
 throw new Error('current_control_readiness_observation_cap');
}
