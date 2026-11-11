#!/usr/bin/env python3
"""Fetch checksum-pinned test rootfs and APKv3 packaging tool. No system install."""
import argparse,hashlib,io,json,pathlib,tarfile,urllib.request

PINS = {
 'apk': {
  'url': 'https://dl-cdn.alpinelinux.org/alpine/v3.23/main/x86_64/apk-tools-static-3.0.9-r0.apk',
  'sha256': 'ea77b2533566e70c9566c03748199b79348010c3199ba02d97e0634cf0fa9ef7',
 },
 'rootfs': {
  'url': 'https://downloads.openwrt.org/releases/25.12.5/targets/x86/64/openwrt-25.12.5-x86-64-generic-targz-rootfs.tar.gz',
  'sha256': '4f191a9684949b15db02bb1ccdacaa8192ffb4598ce92e70b5337ca50df7912a',
 },
}

def fetch(pin):
 with urllib.request.urlopen(pin['url'],timeout=90) as response: data=response.read()
 if hashlib.sha256(data).hexdigest()!=pin['sha256']: raise RuntimeError('Pinned download checksum mismatch')
 return data

def bootstrap(destination):
 destination=pathlib.Path(destination).resolve();destination.mkdir(parents=True,exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(fetch(PINS['apk'])),mode='r:gz') as archive:
  member=archive.getmember('sbin/apk.static')
  if not member.isfile(): raise RuntimeError('Unexpected apk.static archive member')
  executable=destination/'apk';executable.write_bytes(archive.extractfile(member).read());executable.chmod(0o755)
 root=destination/'openwrt-root';root.mkdir(exist_ok=False)
 with tarfile.open(fileobj=io.BytesIO(fetch(PINS['rootfs'])),mode='r:gz') as archive:
  members=[m for m in archive.getmembers() if m.name.lstrip('./').startswith('www/') and (m.isfile() or m.isdir())]
  archive.extractall(root,members=members,filter='data')
 return destination

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('destination');args=parser.parse_args()
 print(bootstrap(args.destination))
