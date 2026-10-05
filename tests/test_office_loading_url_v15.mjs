import assert from 'node:assert/strict';
import {sameOfficeLoadingURL,withoutOfficeNavigationHints} from '../tools/office_loading_url_v15.mjs';
const base='https://onedrive.live.com/personal/0123456789abcdef/_layouts/15/Doc.aspx?sourcedoc=%7B11111111-1111-1111-1111-111111111111%7D&file=source.pptx&action=edit';
let tests=0;
for(const hints of ['', '&CT=1791175537001','&OR=ItemsView','&CT=1791175537001&OR=ItemsView']){assert.equal(sameOfficeLoadingURL(base+hints,base),true);tests++;}
for(const actual of [base.replace('0123456789abcdef','0123456789abcdea'),base.replace('11111111-1111','11111112-1111'),base.replace('source.pptx','other.pptx'),base.replace('onedrive.live.com','other.invalid'),base+'&other=changed',base+'#changed']){assert.equal(sameOfficeLoadingURL(actual,base),false);tests++;}
for(const hints of ['&CT=abc','&OR=Other','&CT=1&CT=2','&OR=ItemsView&OR=ItemsView','&action=edit','&%43T=1']){assert.throws(()=>withoutOfficeNavigationHints(base+hints));tests++;}
assert.throws(()=>sameOfficeLoadingURL('about:blank',base));tests++;
console.log(JSON.stringify({tests,passed:true,only_CT_decimal_and_OR_ItemsView_ignored:true,duplicate_or_other_changes_rejected:true,native_calls:0}));
