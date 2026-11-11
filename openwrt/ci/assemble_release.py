#!/usr/bin/env python3
"""Create checksums, source archive and build provenance for a validated build."""
import argparse,hashlib,json,pathlib,subprocess


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def mobile_validation(plan,out):
 try:mobile=json.loads((out/'mobile-check.json').read_text())
 except (OSError,ValueError) as error:raise RuntimeError('Missing mobile-browser validation report') from error
 if mobile.get('commit')!=plan['release_commit'] or mobile.get('core_version')!=plan['core_version'] or mobile.get('passed') is not True or mobile.get('viewports')!=[320,390,768,844,932,1280]:
  raise RuntimeError('Missing matching mobile-browser validation; refusing to assemble a release')
 return mobile


def assemble(plan,out):
 out.mkdir(parents=True,exist_ok=True)
 mobile=mobile_validation(plan,out)
 archive=out/plan['source_archive']
 with archive.open('wb') as target:
  subprocess.run(['git','archive','--format=tar.gz','--prefix=hongguo-openwrt/','HEAD'],stdout=target,check=True)
 info=dict(plan)
 info['mobile_browser_checks']=mobile
 info.update({'architecture':'x86_64','goamd64':'v1','cgo':False,'package_sha256':digest(out/plan['package']),
              'source_sha256':digest(archive),'go':subprocess.check_output(['go','version'],text=True).strip(),
              'verification':'Go tests, standalone HTTP smoke, matching LuCI JS DOM tests, APKv3 verification. No router or live playback acceptance.'})
 (out/'BUILD-INFO.json').write_text(json.dumps(info,indent=2)+'\n')
 (out/'INSTALL-zh-CN.txt').write_text('红果短剧 OpenWrt 自动构建 '+plan['package_version']+'\n\n'
  '适用 OpenWrt 25.12.x / x86_64（J1900）。上传 APK 到 /tmp 后执行：\n'
  'apk add --allow-untrusted /tmp/'+plan['package']+'\n\n'
  '入口：服务 → 红果短剧。先设置观看密码，再启用并保存应用。\n'
  '观看：http://OpenWrt的LAN_IP:8797/ ，用户名 hongguo。\n'
  '默认缓存 64 MiB、单文件上限 32 MiB、视频准备并发 1。\n'
  '自动测试通过不代表已完成电视或路由器实机播放验收。\n'
  '源码与完整安装说明：'+ 'https://github.com/'+plan['repository']+'/tree/'+plan['release_commit']+'/openwrt\n')
 names=[plan['package'],plan['source_archive'],'BUILD-INFO.json','INSTALL-zh-CN.txt']
 (out/'SHA256SUMS').write_text(''.join(digest(out/name)+'  '+name+'\n' for name in names))
 (out/'release-notes.md').write_text('自动构建 OpenWrt 25.12 x86_64 安装包，兼容 J1900。\n\n'
  '- 上游版本：`'+plan['upstream_tag']+'`\n- 上游提交：`'+plan['upstream_commit']+'`\n'
  '- 构建提交：`'+plan['release_commit']+'`\n- 包版本：`'+plan['package_version']+'`\n\n'
  '安装后进入 **服务 → 红果短剧**，设置观看密码并启用。\n\n'
  '```sh\napk add --allow-untrusted /tmp/'+plan['package']+'\n```\n\n'
  '包含源码、SHA256 校验和及构建信息。CI 验证不替代路由器和电视真实播放验收。\n')
 return names+['SHA256SUMS']

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True,type=pathlib.Path);p.add_argument('--out',required=True,type=pathlib.Path);a=p.parse_args()
 print('\n'.join(assemble(json.loads(a.plan.read_text()),a.out)))
