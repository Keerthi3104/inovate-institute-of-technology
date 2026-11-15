import copy
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app

class WebsiteTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.password = os.urandom(16).hex()
        config = patch.dict(os.environ, {'INSTITUTE_DB':temp.name+'/db', 'INSTITUTE_ADMIN_PASSWORD':self.password})
        config.start()
        self.addCleanup(config.stop)
        self.cookie = ''

    def request(self, path, method='GET', data=None):
        body = json.dumps(data).encode() if data is not None else b''
        env = {'PATH_INFO':path, 'REQUEST_METHOD':method, 'CONTENT_LENGTH':str(len(body)),
               'CONTENT_TYPE':'application/json', 'wsgi.input':io.BytesIO(body),'HTTP_COOKIE':self.cookie}
        received = []
        payload = b''.join(app.application(env,lambda s,h:received.extend((s,dict(h)))))
        if 'Set-Cookie' in received[1]:
            self.cookie = received[1]['Set-Cookie'].split(';')[0]
        return int(received[0][:3]), json.loads(payload) if path.startswith('/api/') else payload

    def login(self):
        self.assertEqual(self.request('/api/login','POST',{'password':self.password})[0],200)

    def test_assets_and_catalogue(self):
        for path in ['/', '/site.js','/admin.js','/style.css','/favicon.svg']:
            self.assertEqual(self.request(path)[0],200)
        status, public = self.request('/api/content')
        self.assertEqual(status,200)
        self.assertEqual(len(public['data']['courses']),12)
        self.assertEqual(len(public['data']['programs']),4)
        self.assertEqual(public['data']['site']['name'],'Inovate Institute of Technology')
        for key, value in public['data'].items():
            app.validate(value,app.DEFAULTS[key])
        self.assertEqual(self.request('/content.json')[0],404)

    def test_admissions_and_session(self):
        entry=dict(name='Test learner', email='student@example.com',phone='+91 99000 00001',interest='Sample',
                   intent='College partnership',mode='Hybrid',batch='Weekend',callback='Morning',notes='A question',
                   consent=True,requestId='c'*32)
        for changes in ({'email':'invalid'},{'consent':False},{'phone':'       '}):
            self.assertEqual(self.request('/api/enquiries','POST',entry|changes)[0],400)
        status,result=self.request('/api/enquiries','POST',entry)
        self.assertEqual(status,200)
        self.assertEqual(self.request('/api/enquiries','POST',entry)[1],result)
        self.assertEqual(self.request('/api/inbox')[0],401)
        self.assertEqual(self.request('/api/login','POST',{'password':'wrong'})[0],401)
        self.login()
        items=self.request('/api/inbox')[1]
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['id'],result['reference'])
        for status in ('Contacted','Closed'):
            self.assertEqual(self.request('/api/status','PUT',{'id':result['reference'],'status':status})[0],200)
            self.assertEqual(self.request('/api/inbox')[1][0]['status'],status)
        self.request('/api/logout','POST',{})
        self.assertEqual(self.request('/api/inbox')[0],401)

    def test_publish_and_conflict(self):
        content=self.request('/api/content')[1]
        courses=copy.deepcopy(content['data']['courses'])
        record=copy.deepcopy(courses[0])
        record.update(id='test-track',title='Test track')
        courses.append(record)
        draft=dict(section='courses',version=content['version'],value=courses)
        self.assertEqual(self.request('/api/content','PUT',draft)[0],401)
        self.login()
        self.assertEqual(self.request('/api/content','PUT',draft)[0],200)
        self.assertEqual(self.request('/api/content','PUT',draft)[0],409)
        updated=self.request('/api/content')[1]
        self.assertEqual(updated['data']['courses'][-1]['title'],'Test track')
        draft['version']=updated['version']
        draft['value'].pop()
        self.assertEqual(self.request('/api/content','PUT',draft)[0],200)
        self.assertEqual(len(self.request('/api/content')[1]['data']['courses']),12)

    def test_invalid_content(self):
        self.login()
        for k,v in [('courses',[]),('home',{'heading':'missing intro'}),('site',dict(app.DEFAULTS['site'],mapUrl='javascript:0'))]:
            self.assertEqual(self.request('/api/content','PUT',dict(section=k,value=v,version=1))[0],400)
        self.assertEqual(self.request('/api/content')[1]['version'],1)

if __name__=='__main__':
    unittest.main()
