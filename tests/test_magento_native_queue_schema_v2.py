"""Execute the actual read queries against the pinned 2.4.6 column layout."""
import re,sqlite3,unittest
from contextlib import closing
from magento_catalog_factory.native_queue_profile_v2 import QUEUE_READ_PHP

class QueueSchemaTests(unittest.TestCase):
 def test_actual_three_selects_use_native_message_id_and_status_foreign_key(self):
  with closing(sqlite3.connect(':memory:')) as db:
   db.executescript('''
    CREATE TABLE queue_message(id INTEGER PRIMARY KEY,topic_name TEXT,body TEXT);
    CREATE TABLE queue_message_status(id INTEGER PRIMARY KEY,message_id INTEGER,queue_id INTEGER,status INTEGER,updated_at TEXT);
    CREATE TABLE magento_operation(id INTEGER PRIMARY KEY,bulk_uuid TEXT,topic_name TEXT,status INTEGER,error_code INTEGER,result_message TEXT,serialized_data TEXT);
    INSERT INTO queue_message VALUES(17,'product_action_attribute.update','private payload');
    INSERT INTO queue_message VALUES(18,'unrelated.topic','untouched');
    INSERT INTO queue_message_status VALUES(1,17,9,4,'2026-10-01');
    INSERT INTO queue_message_status VALUES(2,18,9,2,'2026-10-01');
    INSERT INTO magento_operation VALUES(3,'native-bulk','product_action_attribute.update',1,NULL,NULL,'private operation');
   ''')
   queries=re.findall(r'\$db->query\("([^"\n]+)"\)->fetchAll',QUEUE_READ_PHP)
   self.assertEqual(len(queries),3)
   results=[]
   for query in queries:
    cursor=db.execute(query.replace('{$p}',''));results.append(([d[0] for d in cursor.description],cursor.fetchall()))
   self.assertEqual(results[0][0],['message_id','topic_name','body']);self.assertEqual(results[0][1],[(17,'product_action_attribute.update','private payload')])
   self.assertEqual(results[1][1],[(17,9,4,'2026-10-01')]);self.assertEqual(results[2][1][0][0],3)
   with self.assertRaises(sqlite3.OperationalError):db.execute('SELECT message_id FROM queue_message')
if __name__=='__main__':unittest.main()
