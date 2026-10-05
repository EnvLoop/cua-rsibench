/* Exact parent heading/card readiness; read-only polling replaces builtin waits. */
const check=(ok,code)=>{if(!ok)throw new Error(code);};
export async function waitOwnedParentReady({tab,parentURL,heading,card,retain,clock=Date.now,maximumMs=10000,maximumObservations=12,observeIntervalMs=900,pause=ms=>new Promise(resolve=>setTimeout(resolve,ms))}){
 const began=clock();
 const current=async()=>check(clock()-began<maximumMs&&await tab.url()===parentURL,'parent_navigation_URL_or_deadline_changed');
 for(let i=0;i<maximumObservations;i++){
  await current();const snapshot=await tab.playwright.domSnapshot();await retain(snapshot,i);await current();
  const headings=await heading.count(),cards=await card.count();
  check(headings<=1,'parent_heading_ambiguous');check(cards<=1,'parent_card_ambiguous');
  if(headings===1&&cards===1&&await heading.isVisible()&&await card.isVisible()){
   await current();return {readonly:true,parent_heading_ready:true,exact_card_ready:true,observations:i+1,elapsed_ms:clock()-began,maximum_ms:maximumMs};
  }
  if(i+1<maximumObservations)await pause(Math.min(observeIntervalMs,Math.max(0,maximumMs-(clock()-began))));
 }
 throw new Error('parent_navigation_readiness_observation_cap');
}
