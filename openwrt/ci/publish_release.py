#!/usr/bin/env python3
"""Push the tested commit/tag atomically; verify draft assets before publishing."""
import argparse,hashlib,json,pathlib,subprocess,tempfile


def run(*args,capture=False):
 return subprocess.run(args,check=True,text=True,stdout=subprocess.PIPE if capture else None).stdout


def publish(plan,out):
 tag=plan['release_tag'];repository=plan['repository'];commit=plan['release_commit']
 if run('git','rev-parse','HEAD',capture=True).strip()!=commit:raise RuntimeError('Checkout changed after build')
 if run('git','status','--porcelain',capture=True).strip():raise RuntimeError('Checkout is dirty after build')
 local_tag=subprocess.run(['git','rev-parse','--verify','refs/tags/'+tag],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 if local_tag.returncode:run('git','tag',tag,commit)
 if run('git','rev-parse',tag+'^{commit}',capture=True).strip()!=commit:raise RuntimeError('Local release tag mismatch')
 run('gh','auth','setup-git','--hostname','github.com')
 run('git','push','--atomic','origin','HEAD:refs/heads/openwrt','refs/tags/'+tag)
 existing=subprocess.run(['gh','api','repos/'+repository+'/releases/tags/'+tag],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if existing.returncode==0:
  if not json.loads(existing.stdout).get('draft'):raise RuntimeError('Refusing to replace a published release')
 elif '404' in existing.stderr:
  run('gh','release','create',tag,'--repo',repository,'--verify-tag','--target',commit,'--title','OpenWrt '+plan['package_version'],
      '--notes-file',str(out/'release-notes.md'),'--draft')
 else:raise RuntimeError('Cannot query release: '+existing.stderr)
 names=[plan['package'],plan['source_archive'],'BUILD-INFO.json','INSTALL-zh-CN.txt','SHA256SUMS']
 run('gh','release','upload',tag,'--repo',repository,*[str(out/name) for name in names],'--clobber')
 with tempfile.TemporaryDirectory(prefix='openwrt-release-verify-') as directory:
  run('gh','release','download',tag,'--repo',repository,'--dir',directory)
  for name in names:
   remote=pathlib.Path(directory)/name
   if not remote.is_file() or hashlib.sha256(remote.read_bytes()).digest()!=hashlib.sha256((out/name).read_bytes()).digest():
    raise RuntimeError('Uploaded asset checksum mismatch: '+name)
 run('gh','release','edit',tag,'--repo',repository,'--draft=false','--latest')
 print('https://github.com/'+repository+'/releases/tag/'+tag)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True,type=pathlib.Path);p.add_argument('--out',required=True,type=pathlib.Path);a=p.parse_args()
 publish(json.loads(a.plan.read_text()),a.out.resolve())
