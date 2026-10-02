import test from 'node:test';import assert from 'node:assert/strict';import {documentDownloadName,validateDocumentDownload} from '../tools/office_document_download_v4.mjs';import {ooxmlFixture} from './office_ooxml_fixture_v4.mjs';
test('documented native path exact filename and standard browser collision suffix are accepted',()=>{
 assert.deepEqual(documentDownloadName('/private/download/source.pptx','source.pptx'),{nativeBasename:'source.pptx',collisionSuffix:null});
 assert.equal(documentDownloadName('/private/download/source (5).pptx','source.pptx').collisionSuffix,5);
 assert.equal(validateDocumentDownload('/private/download/source (5).pptx',ooxmlFixture('powerpoint-web'),{fileName:'source.pptx',cell:'powerpoint-web'}).structuralContainerVerified,true);
});
test('another document, extension, folder ZIP or unrecognized collision syntax is rejected',()=>{
 for(const file of ['other.pptx','source.zip','source.xlsx','source (0).pptx','source (05).pptx','source-5.pptx','source (5) copy.pptx'])assert.throws(()=>documentDownloadName('/private/download/'+file,'source.pptx'));
});
test('non OOXML, wrong Office main part, truncated or altered ZIP structure is rejected',()=>{
 assert.throws(()=>validateDocumentDownload('/private/source.pptx',Buffer.from('HTML sign in'),{fileName:'source.pptx',cell:'powerpoint-web'}));
 assert.throws(()=>validateDocumentDownload('/private/source.pptx',ooxmlFixture('excel-web'),{fileName:'source.pptx',cell:'powerpoint-web'}));
 const bytes=ooxmlFixture('powerpoint-web');assert.throws(()=>validateDocumentDownload('/private/source.pptx',bytes.subarray(0,-1),{fileName:'source.pptx',cell:'powerpoint-web'}));bytes[0]=0;assert.throws(()=>validateDocumentDownload('/private/source.pptx',bytes,{fileName:'source.pptx',cell:'powerpoint-web'}));
});
