"""Two explicit public synthetic RFQs. Existing admin only, no new user accounts."""
import base64,json
from pathlib import Path
from .config import canonical

def cases():
 return [{'id':'PUBLIC-TRAIN-001','vendor':'Public Synthetic Supplier One','sku':'PUBLIC-PART-001','name':'Public training replacement part',
   'initial_qty':5.0,'expected_qty':5.0,'initial_price':17.0,'expected_price':12.0},
   {'id':'PUBLIC-WRONG-002','vendor':'Public Synthetic Supplier Two','sku':'PUBLIC-PART-002','name':'Public training unrelated part',
   'initial_qty':6.0,'expected_qty':6.0,'initial_price':18.0,'expected_price':13.0}]

def document(case):
 from reportlab.pdfgen import canvas
 import io
 out=io.BytesIO();c=canvas.Canvas(out,invariant=True);c.setTitle('Public synthetic supplier confirmation')
 for y,text in [(790,'PUBLIC NONTRAINING REFERENCE DEMO'),(750,case['id']),(720,case['vendor']),
                (680,case['sku']),(640,'Quantity: '+str(case['expected_qty'])),(610,'Unit price: '+str(case['expected_price']))]:c.drawString(48,y,text)
 c.save();return out.getvalue()

def seed(factory):
 rpc=factory.OdooRPC();company=rpc.call('res.company','search_read',[],fields=['id'],limit=1)[0]['id']
 gold={}
 for case in cases():
  vendor=rpc.call('res.partner','create',{'name':case['vendor'],'supplier_rank':1,'comment':'Public synthetic TRAIN-only demo'})
  product=rpc.call('product.product','create',{'name':case['name'],'default_code':case['sku'],'type':'consu','purchase_ok':True})
  uom=rpc.call('product.product','read',[product],fields=['uom_po_id'])[0]['uom_po_id'][0]
  order=rpc.call('purchase.order','create',{'name':case['id'],'origin':'PUBLIC-TRAIN-DEMO','partner_id':vendor,
    'order_line':[(0,0,{'product_id':product,'product_uom':uom,'name':case['sku']+' - '+case['name'],
      'product_qty':case['initial_qty'],'price_unit':case['initial_price'],'date_planned':'2025-05-01 12:00:00'})]})
  line=rpc.call('purchase.order.line','search_read',[['order_id','=',order]],fields=['id','product_id'],limit=1)[0]
  rpc.call('ir.attachment','create',{'name':case['id']+'-source.pdf','type':'binary','res_model':'purchase.order','res_id':order,
     'datas':base64.b64encode(document(case)).decode(),'description':'Public synthetic known-answer demo; not a hidden evaluation case'})
  gold[case['id']]={'order_id':order,'partner_id':vendor,'state':'draft','lines':[{'line_id':line['id'],'product_id':product,
      'expected':{'qty':case['expected_qty'],'price':case['expected_price'],'date':'2025-05-01'},
      'initial':{'qty':case['initial_qty'],'price':case['initial_price'],'date':'2025-05-01'}}]}
 factory.PRIVATE.mkdir(mode=0o700,exist_ok=True)
 p=factory.PRIVATE/'development_gold.json';p.write_bytes(canonical(gold));p.chmod(0o600)
 p=factory.PRIVATE/'actor_credentials.json';p.write_bytes(canonical({'login':'admin','password':factory.local_config()['ODOO_ADMIN_PASSWORD']}));p.chmod(0o600)
 return gold
