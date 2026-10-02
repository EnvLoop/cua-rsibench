/* Actual documented download.path() proof; no HTTP suggested filename claim. */
import path from 'node:path';
const check=(v,code)=>{if(!v)throw new Error(code);};
export function documentDownloadName(nativePath,fileName){
 check(typeof nativePath==='string'&&typeof fileName==='string'&&path.basename(fileName)===fileName,'native_download_filename_invalid');
 const name=path.basename(nativePath),extension=path.extname(fileName),stem=fileName.slice(0,-extension.length);
 check(['.pptx','.xlsx'].includes(extension)&&!name.toLowerCase().endsWith('.zip'),'native_download_not_document_or_folder_zip');
 if(name===fileName)return {nativeBasename:name,collisionSuffix:null};
 const escaped=stem.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),match=name.match(new RegExp('^'+escaped+' \\(([1-9][0-9]*)\\)'+extension.replace('.','\\.')+'$'));
 check(match&&Number.isSafeInteger(Number(match[1])),'native_download_unrecognized_or_different_document_name');
 return {nativeBasename:name,collisionSuffix:Number(match[1])};
}
export function validateOoxmlContainer(raw,cell){
 const bytes=Buffer.from(raw);check(bytes.length>=98&&bytes.length<=50000000&&bytes.readUInt32LE(0)===0x04034b50,'native_download_not_ooxml_zip');
 let end=-1;for(let p=bytes.length-22;p>=Math.max(0,bytes.length-65557);p--)if(bytes.readUInt32LE(p)===0x06054b50&&p+22+bytes.readUInt16LE(p+20)===bytes.length){end=p;break;}
 check(end>=0&&bytes.readUInt16LE(end+4)===0&&bytes.readUInt16LE(end+6)===0,'native_ooxml_end_record_invalid');
 const count=bytes.readUInt16LE(end+10),size=bytes.readUInt32LE(end+12),offset=bytes.readUInt32LE(end+16);
 check(count>=3&&count<=20000&&bytes.readUInt16LE(end+8)===count&&offset+size===end,'native_ooxml_directory_invalid');
 const names=new Set();let cursor=offset,total=0;
 for(let k=0;k<count;k++){
  check(cursor+46<=end&&bytes.readUInt32LE(cursor)===0x02014b50,'native_ooxml_member_directory_invalid');
  const flags=bytes.readUInt16LE(cursor+8),method=bytes.readUInt16LE(cursor+10),compressed=bytes.readUInt32LE(cursor+20),plain=bytes.readUInt32LE(cursor+24),n=bytes.readUInt16LE(cursor+28),extra=bytes.readUInt16LE(cursor+30),comment=bytes.readUInt16LE(cursor+32),local=bytes.readUInt32LE(cursor+42);
  check(!(flags&1)&&[0,8].includes(method)&&n>0&&cursor+46+n+extra+comment<=end&&local+30<=offset&&bytes.readUInt32LE(local)===0x04034b50,'native_ooxml_member_header_invalid');
  const name=bytes.toString('utf8',cursor+46,cursor+46+n);check(!name.startsWith('/')&&!name.includes('\\')&&!name.split('/').includes('..')&&!names.has(name),'native_ooxml_member_name_invalid');names.add(name);
  const localN=bytes.readUInt16LE(local+26),localExtra=bytes.readUInt16LE(local+28);
  check(bytes.readUInt16LE(local+6)===flags&&bytes.readUInt16LE(local+8)===method&&bytes.toString('utf8',local+30,local+30+localN)===name&&local+30+localN+localExtra+compressed<=offset,'native_ooxml_member_bytes_invalid');
  total+=plain;check(total<=200000000,'native_ooxml_expansion_unbounded');cursor+=46+n+extra+comment;
 }
 const main=cell==='powerpoint-web'?'ppt/presentation.xml':cell==='excel-web'?'xl/workbook.xml':null;
 check(cursor===end&&main&&names.has('[Content_Types].xml')&&names.has('_rels/.rels')&&names.has(main),'native_zip_is_not_exact_office_document');
 return {memberCount:count,mainPart:main,structuralContainerVerified:true};
}
export function validateDocumentDownload(nativePath,raw,{fileName,cell}){
 const name=documentDownloadName(nativePath,fileName);const ooxml=validateOoxmlContainer(raw,cell);return {...name,...ooxml};
}
