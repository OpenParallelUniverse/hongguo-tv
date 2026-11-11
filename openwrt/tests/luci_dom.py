#!/usr/bin/env python3
"""Exercise genuine OpenWrt LuCI JavaScript in jsdom; mock only ubus JSON-RPC.
Usage: python3 luci_dom.py /path/to/extracted/openwrt/rootfs
"""
import copy,http.server,json,pathlib,sys,threading
import subprocess,os
root=pathlib.Path(sys.argv[1]).resolve()
plugin=pathlib.Path(__file__).resolve().parents[1]/'files'
values={'hongguo':{'main':{'.name':'main','.type':'hongguo','.anonymous':False,'.index':0,'enabled':'0','listen':'0.0.0.0','port':'8797','password':'','cache_dir':'/tmp/hongguo-media','cache_mb':'64','max_media_mb':'32','prepare_concurrency':'1'}},'luci':{}}
calls=[]
class Handler(http.server.SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(root/'www'),**kw)
 def log_message(self,*a):pass
 def do_GET(self):
  if self.path=='/':
   env={'media':'/luci-static/bootstrap','resource':'/luci-static/resources','scriptname':'/cgi-bin/luci','pathinfo':'/admin/services/hongguo','documentroot':'/www','requestpath':['admin','services','hongguo'],'dispatchpath':['admin','services','hongguo'],'pollinterval':5,'ubuspath':'/ubus/','sessionid':'0'*32,'token':'test','nodespec':{'action':{'type':'view','path':'hongguo/settings'},'readonly':False}}
   html='''<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/luci-static/bootstrap/cascade.css"><script src="/luci-static/resources/cbi.js"></script><script src="/luci-static/resources/luci.js"></script></head><body><div id="maincontent" style="margin:32px"><div id="view"></div></div><script>window.L=new LuCI(ENV);L.require('view.hongguo.settings');</script></body></html>'''.replace('ENV',json.dumps(env))
   self.send_response(200);self.end_headers();self.wfile.write(html.encode());return
  if self.path.split('?')[0]=='/luci-static/resources/view/hongguo/settings.js':
   self.send_response(200);self.send_header('Content-Type','application/javascript');self.end_headers();self.wfile.write((plugin/'www/luci-static/resources/view/hongguo/settings.js').read_bytes());return
  super().do_GET()
 def do_POST(self):
  data=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
  def respond(req):
   if req.get('method')=='list':return {'jsonrpc':'2.0','id':req['id'],'result':{}}
   params=req.get('params',[]);obj=params[1];method=params[2];args=params[3] if len(params)>3 else {};calls.append((obj,method,args));result={}
   if obj=='session':result={'access':True}
   elif obj=='uci' and method=='get':result={'values':copy.deepcopy(values.get(args.get('config'),{}))}
   elif obj=='uci' and method=='set':values[args['config']][args['section']].update(args['values'])
   elif obj=='uci' and method=='delete':
    for key in args.get('options',[]):values[args['config']][args['section']].pop(key,None)
   elif obj=='uci' and method=='changes':result={'changes':{}}
   elif obj=='file' and method=='list':result={'entries':[]}
   elif obj=='file' and method=='exec':result={'code':0,'stdout':'','stderr':''}
   elif obj=='service':result={'hongguo':{'instances':{}}}
   return {'jsonrpc':'2.0','id':req['id'],'result':[0,result]}
  response=[respond(r) for r in data] if isinstance(data,list) else respond(data)
  self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(response).encode())
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 env=dict(os.environ)
 subprocess.run(['node',str(pathlib.Path(__file__).with_name('luci_dom.cjs')),'http://127.0.0.1:%d/'%server.server_port],env=env,check=True)
 assert values['hongguo']['main']['port']=='8877',values
 assert values['hongguo']['main']['password']=='test-password-123',values
 assert any(obj=='file' and method=='exec' and args.get('params')==['restart'] for obj,method,args in calls),calls[-8:]
 print('PASS: UCI RPC writes and init-script restart arguments verified')
finally:server.shutdown()
