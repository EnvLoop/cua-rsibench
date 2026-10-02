/* Structural OOXML ZIP fixture only; never a native qualification artifact. */
export function ooxmlFixture(cell){
 const names=['[Content_Types].xml','_rels/.rels',cell==='powerpoint-web'?'ppt/presentation.xml':'xl/workbook.xml'];const locals=[],central=[];let offset=0;
 for(const name of names){const n=Buffer.from(name),data=Buffer.from('<fixture/>'),head=Buffer.alloc(30);head.writeUInt32LE(0x04034b50,0);head.writeUInt16LE(20,4);head.writeUInt32LE(data.length,18);head.writeUInt32LE(data.length,22);head.writeUInt16LE(n.length,26);locals.push(head,n,data);
  const entry=Buffer.alloc(46);entry.writeUInt32LE(0x02014b50,0);entry.writeUInt16LE(20,4);entry.writeUInt16LE(20,6);entry.writeUInt32LE(data.length,20);entry.writeUInt32LE(data.length,24);entry.writeUInt16LE(n.length,28);entry.writeUInt32LE(offset,42);central.push(entry,n);offset+=head.length+n.length+data.length;
 }
 const directory=Buffer.concat(central),end=Buffer.alloc(22);end.writeUInt32LE(0x06054b50,0);end.writeUInt16LE(names.length,8);end.writeUInt16LE(names.length,10);end.writeUInt32LE(directory.length,12);end.writeUInt32LE(offset,16);return Buffer.concat([...locals,directory,end]);
}
