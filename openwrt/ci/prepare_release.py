#!/usr/bin/env python3
"""Merge a published upstream version into a clean OpenWrt checkout; no push."""
import argparse,json,os,pathlib,re,subprocess,urllib.error,urllib.request

UPSTREAM='aston314/hongguo-tv'
RELEASES='aston314/hongguo-tv-releases'
TAG_RE=re.compile(r'v([0-9]+\.[0-9]+\.[0-9]+)\Z')


def git(repo,*args,check=True):
 result=subprocess.run(['git','-C',str(repo),*args],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if check and result.returncode: raise RuntimeError('git '+args[0]+' failed: '+result.stderr.strip())
 return result.stdout.strip() if check else result


def github_json(repository,path,missing=False):
 request=urllib.request.Request('https://api.github.com/repos/'+repository+'/'+path,headers={'Accept':'application/vnd.github+json','User-Agent':'hongguo-openwrt-ci'})
 if os.environ.get('GH_TOKEN'): request.add_header('Authorization','Bearer '+os.environ['GH_TOKEN'])
 try:
  with urllib.request.urlopen(request,timeout=45) as response:return json.load(response)
 except urllib.error.HTTPError as error:
  if missing and error.code==404:return None
  raise RuntimeError('GitHub API returned HTTP '+str(error.code)) from None


def select_upstream(tag):
 if not tag:
  release=github_json(RELEASES,'releases/latest')
  if release.get('draft') or release.get('prerelease'):raise RuntimeError('Expected a published stable upstream release')
  tag=release['tag_name']
 if not TAG_RE.fullmatch(tag):raise ValueError('Upstream tag must be vMAJOR.MINOR.PATCH')
 return tag


def merge_upstream(repo,tag,source_url):
 original=git(repo,'rev-parse','HEAD')
 tracked_file=repo/'openwrt/UPSTREAM.json'
 tracked=json.loads(tracked_file.read_text()) if tracked_file.exists() else None
 if tracked and TAG_RE.fullmatch(tracked.get('tag','')):
  current=tuple(map(int,tracked['tag'][1:].split('.')))
  requested=tuple(map(int,tag[1:].split('.')))
  if requested<current:raise RuntimeError('Refusing to label newer source with an older upstream version')
 if git(repo,'status','--porcelain'):raise RuntimeError('Refusing to merge into a dirty checkout')
 git(repo,'fetch','--no-tags',source_url,'refs/tags/'+tag)
 upstream=git(repo,'rev-parse','FETCH_HEAD^{commit}')
 if tracked and tracked.get('tag')==tag and tracked.get('commit')!=upstream:
  raise RuntimeError('Upstream tag moved since the last build; manual review required')
 git(repo,'config','user.name','github-actions[bot]')
 git(repo,'config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
 result=git(repo,'merge','--no-ff','--no-edit',upstream,check=False)
 if result.returncode:
  conflicts=git(repo,'diff','--name-only','--diff-filter=U')
  git(repo,'merge','--abort',check=False)
  raise RuntimeError('Upstream merge failed; no branch or release was published. Conflicts: '+(conflicts or result.stderr.strip()))
 state=repo/'openwrt/UPSTREAM.json'
 state.write_text(json.dumps({'repository':UPSTREAM,'tag':tag,'commit':upstream},indent=2)+'\n')
 git(repo,'add','--','openwrt/UPSTREAM.json')
 if git(repo,'diff','--cached','--quiet',check=False).returncode:
  git(repo,'commit','-m','chore(openwrt): track upstream '+tag)
 return original,upstream,git(repo,'rev-parse','HEAD')


def make_plan(repo,tag,source_url,repository,lookup=github_json):
 original,upstream,commit=merge_upstream(repo,tag,source_url)
 revision=(repo/'openwrt/RELEASE').read_text().strip()
 if not re.fullmatch(r'[1-9][0-9]{0,5}',revision):raise ValueError('openwrt/RELEASE must be a positive integer')
 version=TAG_RE.fullmatch(tag).group(1)+'-r'+revision
 release_tag='openwrt-v'+version
 package='luci-app-hongguo-'+version+'_x86_64.apk'
 release=lookup(repository,'releases/tags/'+release_tag,missing=True)
 remote=git(repo,'ls-remote','origin','refs/tags/'+release_tag,'refs/tags/'+release_tag+'^{}')
 remote_refs=dict(line.split()[::-1] for line in remote.splitlines())
 tag_commit=remote_refs.get('refs/tags/'+release_tag+'^{}',remote_refs.get('refs/tags/'+release_tag))
 if tag_commit and tag_commit!=commit:
  raise RuntimeError('Release tag already refers to another commit. Increase openwrt/RELEASE; existing releases are immutable.')
 if tag_commit:
  git(repo,'fetch','--no-tags','origin','refs/tags/'+release_tag+':refs/tags/'+release_tag)
 expected={package,'SHA256SUMS','BUILD-INFO.json','INSTALL-zh-CN.txt','hongguo-openwrt-'+version+'-source.tar.gz'}
 build=True
 if release and not release.get('draft'):
  actual={asset['name'] for asset in release.get('assets',[])}
  if not tag_commit or not expected.issubset(actual):raise RuntimeError('Published release has missing assets or tag; refusing to overwrite it')
  build=False
 return {'build':build,'initial_sha':original,'release_commit':commit,'upstream_tag':tag,'upstream_commit':upstream,
         'release_tag':release_tag,'package_version':version,'core_version':version+'-openwrt',
         'package':package,'source_archive':'hongguo-openwrt-'+version+'-source.tar.gz','repository':repository}


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--repo',type=pathlib.Path,default=pathlib.Path.cwd());parser.add_argument('--tag',default='')
 parser.add_argument('--source-url',default='https://github.com/'+UPSTREAM+'.git');parser.add_argument('--repository',default=os.environ.get('GITHUB_REPOSITORY'))
 parser.add_argument('--output',required=True,type=pathlib.Path);args=parser.parse_args()
 if not args.repository or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',args.repository):parser.error('Invalid destination repository')
 plan=make_plan(args.repo.resolve(),select_upstream(args.tag),args.source_url,args.repository)
 args.output.write_text(json.dumps(plan,indent=2)+'\n')
 if os.environ.get('GITHUB_OUTPUT'):
  with open(os.environ['GITHUB_OUTPUT'],'a') as output:
   for key in ['build','release_tag','package_version','core_version','upstream_tag','release_commit']:
    output.write(key+'='+str(plan[key]).lower()+'\n')
 print(json.dumps(plan,indent=2))

if __name__=='__main__':main()
