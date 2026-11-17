"""Inovate Institute website and admissions content service (Python 3.11+)."""
import datetime as dt
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit
from http.cookies import SimpleCookie
from wsgiref.simple_server import make_server

ROOT = Path(__file__).resolve().parent
DEFAULTS = json.loads((ROOT / 'content.json').read_text(encoding='utf-8'))
SECTIONS = set(DEFAULTS)
STATUS = ('New', 'Contacted', 'Closed')

def fix_mojibake(val):
    if isinstance(val, str):
        return (val.replace('â€“', '–')
                   .replace('â€”', '—')
                   .replace('â€™', '’')
                   .replace('â€˜', '‘')
                   .replace('â€œ', '“')
                   .replace('â€\x9d', '”')
                   .replace('â€\x9c', '“')
                   .replace('â€', '”'))
    if isinstance(val, dict):
        return {k: fix_mojibake(v) for k, v in val.items()}
    if isinstance(val, list):
        return [fix_mojibake(v) for v in val]
    return val

class Error(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message

def check(condition, message, status='400 Bad Request'):
    if not condition:
        raise Error(status, message)

def validate(value, model):
    check(type(value) is type(model), 'Check the field type.')
    if isinstance(model, dict):
        check(value.keys() == model.keys(), 'Required fields are missing.')
        for k, v in model.items():
            validate(value[k], v)
    elif isinstance(model, list):
        check(0 < len(value) <= 800, 'Each list needs 1–800 items.')
        if model:
            for item in value:
                validate(item, model[0])
    elif isinstance(model, str):
        check(0 < len(value.strip()) <= 12000, 'Text fields must contain 1–12000 characters.')

def database():
    path = Path(os.environ.get('INSTITUTE_DB', str(Path.home() / '.inovate-institute' / 'site.sqlite3')))
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript('''CREATE TABLE IF NOT EXISTS content (id INTEGER PRIMARY KEY, version INTEGER, data TEXT);
        CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, expires INTEGER);
        CREATE TABLE IF NOT EXISTS enquiries (id TEXT PRIMARY KEY, created TEXT, status TEXT, data TEXT);
        CREATE TABLE IF NOT EXISTS receipts (request_id TEXT PRIMARY KEY, reference TEXT);
        CREATE TABLE IF NOT EXISTS attempts (ip TEXT, timestamp INTEGER);''')
    db.execute('INSERT OR IGNORE INTO content VALUES (1, 1, ?)', (json.dumps(DEFAULTS, ensure_ascii=False),))
    existing = db.execute('SELECT version, data FROM content WHERE id=1').fetchone()
    if existing and ('â' in existing['data']):
        try:
            cleaned = fix_mojibake(json.loads(existing['data']))
            db.execute('UPDATE content SET data=? WHERE id=1', (json.dumps(cleaned, ensure_ascii=False),))
        except Exception:
            pass
    db.commit()
    return db

def endpoint(env, db, headers):
    path = env['PATH_INFO']
    method = env['REQUEST_METHOD']
    row = db.execute('SELECT version,data FROM content WHERE id=1').fetchone()
    data = json.loads(row['data'])
    def current():
        return {'version':row['version'],'data':data}
    if method == 'GET' and path == '/api/content':
        return current()
    body = {}
    if method in ('POST','PUT'):
        check(env.get('CONTENT_TYPE','').split(';')[0]=='application/json','JSON required.')
        length = int(env.get('CONTENT_LENGTH') or 0)
        check(0 < length <= 1048576, 'Request size is invalid.')
        body = json.loads(env['wsgi.input'].read(length))
        check(isinstance(body,dict),'Expected an object.')
    cookies = SimpleCookie()
    cookies.load(env.get('HTTP_COOKIE',''))
    token = cookies['institute_session'].value if 'institute_session' in cookies else ''
    now = int(time.time())
    secure = '; Secure' if env.get('wsgi.url_scheme')=='https' or os.environ.get('INSTITUTE_HTTPS')=='1' else ''
    if method=='POST' and path=='/api/login':
        password=os.environ.get('INSTITUTE_ADMIN_PASSWORD','')
        check(len(password)>=12,'Set INSTITUTE_ADMIN_PASSWORD on the server (12 or more characters).','503 Service Unavailable')
        ip=env.get('REMOTE_ADDR','')
        db.execute('DELETE FROM attempts WHERE timestamp < ?', (now-600,))
        check(db.execute('SELECT COUNT(*) FROM attempts WHERE ip=?',(ip,)).fetchone()[0]<10,'Try again in ten minutes.','429 Too Many Requests')
        supplied=body.get('password','')
        if not isinstance(supplied,str) or not hmac.compare_digest(password.encode(),supplied.encode()):
            db.execute('INSERT INTO attempts VALUES (?,?)',(ip,now))
            db.commit()
            raise Error('401 Unauthorized','Incorrect password.')
        token=secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires<=?',(now,))
        db.execute('INSERT INTO sessions VALUES (?,?)',(token,now+28800))
        headers.append(('Set-Cookie','institute_session='+token+'; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800'+secure))
        return {'ok':True}
    if method=='POST' and path=='/api/enquiries':
        fields=('name','email','phone','interest','intent','mode','batch','callback','notes')
        for key in fields:
            check(isinstance(body.get(key),str) and len(body[key])<=2000,'Check '+key+'.')
        check(body['name'].strip() and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',body['email']) and re.fullmatch(r'[+\d ()-]{7,22}',body['phone']) and 7<=sum(x.isdigit() for x in body['phone'])<=15 and body.get('consent') is True,'Check your contact details and consent.')
        request_id=body.get('requestId','')
        check(isinstance(request_id,str) and re.fullmatch(r'[a-f0-9]{32}',request_id),'Invalid request identifier.')
        db.execute('BEGIN IMMEDIATE')
        previous=db.execute('SELECT reference FROM receipts WHERE request_id=?',(request_id,)).fetchone()
        if previous:
            return {'reference':previous[0]}
        ref='IIT-'+secrets.token_hex(6).upper()
        db.execute('INSERT INTO receipts VALUES (?,?)',(request_id,ref))
        db.execute('INSERT INTO enquiries VALUES (?,?,?,?)',(ref,dt.datetime.now(dt.timezone.utc).isoformat(),'New',json.dumps({k:body[k] for k in (*fields,'consent')})))
        return {'reference':ref}
    check(db.execute('SELECT 1 FROM sessions WHERE token=? AND expires>?',(token,now)).fetchone(),'Sign in to continue.','401 Unauthorized')
    if method=='POST' and path=='/api/logout':
        db.execute('DELETE FROM sessions WHERE token=?',(token,))
        headers.append(('Set-Cookie','institute_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'+secure))
        return {'ok':True}
    if method=='GET' and path=='/api/inbox':
        return [dict(id=r['id'],created=r['created'],status=r['status'],**json.loads(r['data'])) for r in db.execute('SELECT * FROM enquiries ORDER BY created DESC')]
    if method=='PUT' and path=='/api/status':
        check(body.get('status') in STATUS,'Invalid status.')
        check(db.execute('UPDATE enquiries SET status=? WHERE id=?',(body['status'],body.get('id'))).rowcount,'Reference was not found.')
        return {'ok':True}
    if method=='PUT' and path=='/api/content':
        key=body.get('section')
        check(isinstance(key,str) and key in SECTIONS,'Unknown section.')
        value=body.get('value')
        validate(value,DEFAULTS[key])
        if key in ('courses','programs','whyUsPoints'):
            ids=[x['id'] for x in value]
            check(len(set(ids))==len(ids) and all(re.fullmatch(r'[a-z0-9-]+',i) for i in ids),'IDs must be unique lowercase slugs.')
        if key=='nav':
            check({x['to'] for x in value}=={x['to'] for x in DEFAULTS[key]} and len(value)==len(DEFAULTS[key]),'Keep one entry per public page.')
        if key=='site':
            for url in [value['officialWebsite'],value['mapUrl'],*value['socials'].values()]:
                check(urlsplit(url).scheme in ('http','https') and urlsplit(url).netloc,'Enter a complete web address.')
        data[key]=value
        updated=db.execute('UPDATE content SET data=?,version=version+1 WHERE id=1 AND version=?',(json.dumps(data),body.get('version')))
        check(updated.rowcount,'Another editor published first. Reload before editing again.','409 Conflict')
        return {'version':row['version']+1}
    raise Error('404 Not Found','Page not found.')

def application(env,start):
    path=env.get('PATH_INFO','/')
    headers=[('X-Content-Type-Options','nosniff'),('Cache-Control','no-store')]
    status='200 OK'
    if path.startswith('/api/'):
        mime='application/json'
        try:
            with closing(database()) as db, db:
                result=endpoint(env,db,headers)
        except Error as e:
            status,result=e.status,{'error':e.message}
        except (ValueError,TypeError,KeyError):
            status,result='400 Bad Request',{'error':'Invalid request.'}
        except sqlite3.Error:
            status,result='503 Service Unavailable',{'error':'Database unavailable. Try again shortly.'}
        payload=json.dumps(result, ensure_ascii=False).encode('utf-8')
    else:
        files={'/':('index.html','text/html'),'/site.js':('site.js','text/javascript'),'/admin.js':('admin.js','text/javascript'),'/style.css':('style.css','text/css'),'/favicon.svg':('favicon.svg','image/svg+xml'),'/ist-logo.png':('ist-logo.png','image/png'),'/static/ist-logo.png':('ist-logo.png','image/png')}
        if path in files:
            name,mime=files[path]
            payload=(ROOT/'static'/name).read_bytes()
        else:
            status,mime,payload='404 Not Found','text/plain',b'Page not found'
    start(status,headers+[('Content-Type',mime+'; charset=utf-8'),('Content-Length',str(len(payload)))])
    return [payload]

if __name__=='__main__':
    with make_server('127.0.0.1',int(os.environ.get('PORT','8000')),application) as server:
        server.serve_forever()
