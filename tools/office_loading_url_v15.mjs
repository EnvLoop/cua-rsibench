/* Only observed Office navigation hints may disappear before actor binding. */
const check=(ok,code)=>{if(!ok)throw new Error(code);};
export function withoutOfficeNavigationHints(raw){
 check(typeof raw==='string','office_loading_URL_invalid');const url=new URL(raw);
 check(url.protocol==='https:'&&!url.username&&!url.password,'office_loading_URL_invalid');
 const hashAt=raw.indexOf('#'),end=hashAt<0?raw.length:hashAt,queryAt=raw.indexOf('?');
 if(queryAt<0||queryAt>=end)return raw;
 const seen=new Set(),kept=[];
 for(const pair of raw.slice(queryAt+1,end).split('&')){
  check(pair.length>0,'office_loading_query_invalid');const parsed=[...new URLSearchParams(pair)];check(parsed.length===1,'office_loading_query_invalid');
  const [name,value]=parsed[0];check(name.length>0&&!seen.has(name),'office_loading_duplicate_query');seen.add(name);
  if(name==='CT'){check(pair.startsWith('CT=')&&/^[0-9]+$/.test(value)&&pair==='CT='+value,'office_loading_CT_invalid');}
  else if(name==='OR'){check(pair==='OR=ItemsView'&&value==='ItemsView','office_loading_OR_invalid');}
  else kept.push(pair);
 }
 return raw.slice(0,queryAt)+(kept.length?'?'+kept.join('&'):'')+raw.slice(end);
}
export function sameOfficeLoadingURL(actual,expected){return withoutOfficeNavigationHints(actual)===withoutOfficeNavigationHints(expected);}
