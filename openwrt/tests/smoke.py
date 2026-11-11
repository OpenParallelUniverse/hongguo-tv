#!/usr/bin/env python3
"""Run the real standalone binary without calling upstream content APIs."""
import base64,json,os,pathlib,socket,subprocess,tempfile,time,urllib.request,urllib.error
root=pathlib.Path(__file__).resolve().parents[2]
binary=root/'openwrt/files/usr/bin/hongguo-server'
with tempfile.TemporaryDirectory(prefix='hongguo-smoke-') as temp:
 temp=pathlib.Path(temp);pw=temp/'password';pw.write_text('test-password-123');pw.chmod(0o600)
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 env=dict(os.environ,MINIREEL_CACHE_DIR=str(temp/'cache'),GOMEMLIMIT='192MiB')
 command=[str(binary),'--lan','--listen','127.0.0.1','--port',str(port),'--password-file',str(pw),'--data-dir',str(temp/'data'),'--cache-mb','64','--max-media-mb','32','--prepare-concurrency','1']
 with (temp/'server.log').open('w') as log:
  process=subprocess.Popen(command,env=env,stdout=log,stderr=log)
  def request(path,auth=True,headers=None):
   h=dict(headers or {})
   if auth:h['Authorization']='Basic '+base64.b64encode(b'hongguo:test-password-123').decode()
   req=urllib.request.Request('http://127.0.0.1:%d%s'%(port,path),headers=h)
   try:return urllib.request.urlopen(req,timeout=5)
   except urllib.error.HTTPError as e:return e
  try:
   for attempt in range(50):
    try:
     with request('/api/v1/health') as response:
      assert response.status==200
     break
    except (urllib.error.URLError,ConnectionError):time.sleep(.1)
   else:raise RuntimeError('backend did not start')
   for path in ['/','/api/v1/health','/api/v1/account','/api/v1/library','/minireel-proxy/media/012345678901234567890123.mp4']:
    with request(path,False) as response:assert response.status==401,(path,response.status)
   for path in ['/?platform=desktop','/app.js','/desktop.js','/api/v1/status','/api/v1/account','/api/v1/library']:
    with request(path) as response:
     assert response.status==200,(path,response.status,response.read()[:100])
     if path=='/api/v1/status':assert json.load(response)['version']==os.environ.get('HONGGUO_CORE_VERSION','0.1.0-openwrt')
   with request('/api/v1/library',headers={'Origin':'http://evil.example'}) as response:assert response.status==403
   with request('/api/v1/library',headers={'Host':'evil.example'}) as response:assert response.status==403
   with request('/') as response:assert 'platform=desktop' in response.url
   print('PASS: real binary start, UI/static assets, account/library APIs, mandatory authentication, same-origin/Host rejection, browser-mode redirect')
  finally:
   process.terminate()
   try:process.wait(timeout=5)
   except subprocess.TimeoutExpired:process.kill();process.wait()
