"""作者：Wangyuan；日期：2026-10-29；职责：仅以从零合成输入验证核心与异常路径。"""

import unittest
from catalog import *
class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tools=[{'id':'tool','name':'文本工具','category':'文字','state':'available','actions':{'echo':{'input_fields':['text'],'required_fields':['text'],'max_input_bytes':100}}}]
        self.catalog=Catalog(self.tools)
    def test_search_and_favorites(self):
        self.assertEqual(len(self.catalog.search('文本')),1); self.assertEqual(self.catalog.search(favorites=True),[])
        self.catalog.favorite('tool',True); self.assertEqual(len(self.catalog.search(favorites=True)),1)
    def test_unknown_action_fields_and_budget_denied(self):
        for action,payload in [('send',{'text':'x'}),('echo',{'text':'x','secret':'y'}),('echo',{}),('echo',{'text':'x'*200})]:
            with self.assertRaises(ValueError): self.catalog.validate('tool',action,payload)
    def test_plan_prevalidation_prevents_partial_execution(self):
        called=[]; handler=lambda p: called.append(p) or {'text':'ok'}
        steps=[{'id':'1','tool':'tool','action':'echo','input':{'text':'x'}},{'id':'2','tool':'tool','action':'send','input':{'text':'x'}}]
        with self.assertRaises(ValueError): self.catalog.execute(steps,{('tool','echo'):handler})
        self.assertEqual(called,[])
    def test_plan_result_and_reference_validation(self):
        steps=[{'id':'1','tool':'tool','action':'echo','input':{'text':'x'},'allowed_evidence':['s']}]
        good=self.catalog.execute(steps,{('tool','echo'):lambda p:{'text':p['text'],'evidence':['s']}})
        self.assertEqual(good['state'],'completed')
        bad=self.catalog.execute(steps,{('tool','echo'):lambda p:{'text':'x','evidence':['unknown']}})
        self.assertEqual(bad['state'],'failed')
    def test_module_failure_isolation(self):
        result=load_modules([{'id':'missing','essential':False},{'id':'ok','essential':True}],{'ok':lambda:None})
        self.assertEqual(result['missing']['state'],'unavailable'); self.assertEqual(result['ok']['state'],'available')
        with self.assertRaises(RuntimeError): load_modules([{'id':'missing','essential':True}],{})
    def test_event_order_and_idempotent_conflicts(self):
        store=EventStore(); base={'session':'s','agent':'a','timestamp':'2030-01-01T00:00:00+00:00','type':'task_started','id':'1'}
        self.assertTrue(store.ingest(base)); self.assertFalse(store.ingest(base))
        store.ingest({**base,'id':'2','timestamp':'2030-01-01T00:01:00+00:00','type':'task_complete'})
        self.assertEqual(store.snapshot('2030-01-01T01:00:00+00:00',1)['sessions'][0]['projection']['state'],'completed')
        self.assertFalse(store.snapshot('2030-01-01T01:00:00+00:00',1)['sessions'][0]['stale'])
        with self.assertRaises(ValueError): store.ingest({**base,'type':'failed'})
    def test_active_event_expiry(self):
        store=EventStore(); store.ingest({'session':'s','agent':'a','timestamp':'2030-01-01T00:00:00+00:00','type':'task_started','id':'1'})
        self.assertTrue(store.snapshot('2030-01-01T01:00:00+00:00',1)['sessions'][0]['stale'])

if __name__ == "__main__":
    unittest.main()
