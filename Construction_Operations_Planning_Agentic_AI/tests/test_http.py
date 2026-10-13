import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from app.server import make_server


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.server=make_server(0,Path(self.tmp.name)/'http.sqlite3')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()

    def request(self,path,body=None,headers=None):
        req=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,
              headers={'Content-Type':'application/json',**(headers or {})})
        try:
            with self.opener.open(req,timeout=10) as r:return r.status,r.read()
        except urllib.error.HTTPError as r:return r.code,r.read()

    def test_actual_http_plan_and_csv(self):
        status,raw=self.request('/api/sample');self.assertEqual(status,200)
        p=json.loads(raw)
        status,raw=self.request('/api/plan',{'project':p});self.assertEqual(status,200)
        result=json.loads(raw);self.assertEqual(result['summary']['duration'],31)
        status,raw=self.request('/api/export/csv',{'project':p});self.assertEqual(status,200)
        self.assertIn('A12',json.loads(raw)['content'])
        status,raw=self.request('/api/projects');self.assertEqual(len(json.loads(raw)),1)

    def test_static_bundle_and_traversal(self):
        status,raw=self.request('/');self.assertEqual(status,200)
        self.assertIn(b'BuildPlan',raw)
        status,_=self.request('/../run.py');self.assertEqual(status,404)

    def test_cross_origin_and_bad_request(self):
        status,_=self.request('/api/plan',{'project':{}},{'Origin':'https://untrusted.example'});self.assertEqual(status,403)
        status,raw=self.request('/api/plan',{'project':{}});self.assertEqual(status,422)
        self.assertIn('error',json.loads(raw))

    def test_missing_route(self):
        status,_=self.request('/api/unknown');self.assertEqual(status,404)


if __name__=='__main__':unittest.main(verbosity=2)
