import test from 'node:test';
import assert from 'node:assert/strict';
import {inspectNativeOfficeDocument} from '../tools/office_owned_folder_native_extractor_v2.mjs';
function fixture(){
 const doc={URL:'native-fixture',readyState:'complete',defaultView:{getComputedStyle:()=>({display:'block',visibility:'visible',opacity:'1'})}};
 const body={tagName:'BODY',nodeType:1,parentElement:null,children:[]};
 function element(tag,attrs={},x=20){const e={ownerDocument:doc,tagName:tag,nodeType:1,parentElement:body,children:[],type:attrs.type||'',disabled:false,readOnly:false,isContentEditable:false,textContent:'',getAttribute:k=>attrs[k]??null,hasAttribute:k=>Object.hasOwn(attrs,k),getBoundingClientRect:()=>({x,y:150,width:100,height:30}),contains:other=>e===other};body.children.push(e);return e;}
 const input=element('INPUT',{type:'text'},20),share=element('BUTTON',{'aria-label':'Share'},140),link=element('A',{href:'https://external.example'},260);
 doc.activeElement=input;doc.querySelector=()=>null;doc.querySelectorAll=q=>q==='[role="dialog"]'?[]:[input,share,link];doc.elementFromPoint=x=>x<120?input:x<240?share:link;
 return {doc,input,share,link};
}
test('native read-only DOM projection uses actual geometry/focus and blocks account/navigation controls',()=>{
 const {doc}=fixture();const result=inspectNativeOfficeDocument(doc,{clip:{x:0,y:126,width:1000,height:700},frameOffset:{x:0,y:0}});
 assert.equal(result.targets[0].keyboard,true);assert.equal(result.targets[0].focused,true);assert.equal(result.targets[0].fill_scope,true);assert.deepEqual(result.targets[0].bounds,[20,24,100,30]);
 assert.equal(result.targets[1].enabled,false);assert.equal(result.targets[2].enabled,false);assert.equal(result.editor_surface_observed,true);
 assert.equal(JSON.stringify(result).includes('external.example'),false);assert.equal(JSON.stringify(result).includes('Share'),false);
});
test('obscured actual element remains unsafe; no layout rectangle declares native safety',()=>{
 const {doc}=fixture();doc.elementFromPoint=()=>null;const result=inspectNativeOfficeDocument(doc,{clip:{x:0,y:126,width:1000,height:700},frameOffset:{x:0,y:0}});assert.ok(result.targets.every(t=>t.obscured));
});
