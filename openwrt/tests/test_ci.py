import importlib.util,json,pathlib,subprocess,tempfile,unittest
from unittest import mock

ROOT=pathlib.Path(__file__).resolve().parents[1]

def load(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'ci'/(name+'.py'))
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

prepare=load('prepare_release');publisher=load('publish_release');assembler=load('assemble_release')

class ReleasePlanningTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=pathlib.Path(self.temp.name)
  self.upstream=self.root/'upstream';self.upstream.mkdir();self.command(self.upstream,'init','-b','main')
  self.identity(self.upstream)
  (self.upstream/'core.txt').write_text('original\n');self.command(self.upstream,'add','.');self.command(self.upstream,'commit','-m','base')
  self.base=self.command(self.upstream,'rev-parse','HEAD');self.command(self.upstream,'tag','v1.0.0')
  self.bare=self.root/'fork.git';self.command(self.root,'clone','--bare',str(self.upstream),str(self.bare))
  self.repo=self.root/'work';self.command(self.root,'clone',str(self.bare),str(self.repo));self.identity(self.repo)
  self.command(self.repo,'switch','-c','openwrt');(self.repo/'openwrt').mkdir()
  (self.repo/'openwrt/RELEASE').write_text('2\n')
  (self.repo/'openwrt/UPSTREAM.json').write_text(json.dumps({'repository':prepare.UPSTREAM,'tag':'v1.0.0','commit':self.base},indent=2)+'\n')
  self.command(self.repo,'add','.');self.command(self.repo,'commit','-m','integration');self.command(self.repo,'push','origin','openwrt')
  self.initial=self.command(self.repo,'rev-parse','HEAD')
 def command(self,repo,*args):
  p=subprocess.run(['git','-C',str(repo),*args],check=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE);return p.stdout.strip()
 def identity(self,repo):
  self.command(repo,'config','user.name','Test User');self.command(repo,'config','user.email','test@example.invalid')
 def upstream_release(self):
  (self.upstream/'core.txt').write_text('upstream update\n');self.command(self.upstream,'add','.');self.command(self.upstream,'commit','-m','update');self.command(self.upstream,'tag','v1.0.1')
 def plan(self,tag='v1.0.1',release=None):
  return prepare.make_plan(self.repo,tag,str(self.upstream),'example/fork',lookup=lambda *a,**kw:release)
 def test_new_version_preserves_integration_and_does_not_push(self):
  self.upstream_release();plan=self.plan()
  self.assertTrue(plan['build']);self.assertEqual(plan['package_version'],'1.0.1-r2')
  self.assertEqual((self.repo/'core.txt').read_text(),'upstream update\n');self.assertTrue((self.repo/'openwrt/RELEASE').exists())
  self.assertEqual(self.command(self.bare,'rev-parse','refs/heads/openwrt'),self.initial)
  self.command(self.repo,'merge-base','--is-ancestor',self.initial,plan['release_commit'])
 def test_conflict_aborts_without_changing_branch(self):
  (self.repo/'core.txt').write_text('local incompatible edit\n');self.command(self.repo,'add','.');self.command(self.repo,'commit','-m','local')
  before=self.command(self.repo,'rev-parse','HEAD');self.upstream_release()
  with self.assertRaisesRegex(RuntimeError,'Conflicts: core.txt'):self.plan()
  self.assertEqual(self.command(self.repo,'rev-parse','HEAD'),before)
  self.assertEqual(self.command(self.repo,'status','--porcelain'),'')
  self.assertEqual(self.command(self.bare,'rev-parse','refs/heads/openwrt'),self.initial)
 def test_upstream_ui_changes_preserve_mobile_addons(self):
  local=self.repo/'ui';local.mkdir();(local/'openwrt-mobile.css').write_text('/* fork mobile overrides */\n')
  self.command(self.repo,'add','.');self.command(self.repo,'commit','-m','mobile addon')
  remote=self.upstream/'ui';remote.mkdir();(remote/'app.css').write_text('/* next upstream UI */\n')
  self.upstream_release();self.plan()
  self.assertEqual((local/'openwrt-mobile.css').read_text(),'/* fork mobile overrides */\n')
  self.assertEqual((local/'app.css').read_text(),'/* next upstream UI */\n')
 def test_upstream_workflows_are_excluded_from_source_update(self):
  workflows=self.repo/'.github/workflows';workflows.mkdir(parents=True)
  (workflows/'local.yml').write_text('name: local integration workflow\n')
  self.command(self.repo,'add','.');self.command(self.repo,'commit','-m','own workflow')
  theirs=self.upstream/'.github/workflows';theirs.mkdir(parents=True)
  (theirs/'upstream.yml').write_text('name: upstream-only workflow\n')
  self.upstream_release();self.plan()
  self.assertFalse((workflows/'upstream.yml').exists())
  self.assertEqual((workflows/'local.yml').read_text(),'name: local integration workflow\n')
  self.assertEqual((self.repo/'core.txt').read_text(),'upstream update\n')
 def test_completed_release_is_skipped(self):
  self.upstream_release();plan=self.plan();self.command(self.repo,'tag',plan['release_tag']);self.command(self.repo,'push','origin','openwrt',plan['release_tag'])
  names=[plan['package'],plan['source_archive'],'SHA256SUMS','BUILD-INFO.json','INSTALL-zh-CN.txt']
  result=self.plan(release={'draft':False,'assets':[{'name':name} for name in names]})
  self.assertFalse(result['build'])
 def test_draft_can_resume_after_interrupted_upload(self):
  self.upstream_release();plan=self.plan();self.command(self.repo,'tag',plan['release_tag']);self.command(self.repo,'push','origin','openwrt',plan['release_tag'])
  self.assertTrue(self.plan(release={'draft':True,'assets':[]})['build'])
 def test_existing_tag_cannot_be_reassigned(self):
  self.command(self.repo,'tag','openwrt-v1.0.1-r2');self.command(self.repo,'push','origin','openwrt-v1.0.1-r2');self.upstream_release()
  with self.assertRaisesRegex(RuntimeError,'Increase openwrt/RELEASE'):self.plan()
 def test_incomplete_published_release_is_not_overwritten(self):
  self.upstream_release();plan=self.plan();self.command(self.repo,'tag',plan['release_tag']);self.command(self.repo,'push','origin','openwrt',plan['release_tag'])
  with self.assertRaisesRegex(RuntimeError,'missing assets'):self.plan(release={'draft':False,'assets':[]})
 def test_dirty_worktree_is_rejected(self):
  (self.repo/'core.txt').write_text('unsaved edit\n')
  with self.assertRaisesRegex(RuntimeError,'dirty checkout'):self.plan('v1.0.0')
 def test_downgrade_is_rejected(self):
  with self.assertRaisesRegex(RuntimeError,'older upstream'):self.plan('v0.9.0')
 def test_moved_upstream_tag_requires_review(self):
  self.upstream_release();self.command(self.upstream,'tag','-f','v1.0.0')
  with self.assertRaisesRegex(RuntimeError,'tag moved'):self.plan('v1.0.0')

class InputAndPublicationTests(unittest.TestCase):
 def test_tag_input_cannot_inject_commands_or_references(self):
  for tag in ['v1.2.3;echo bad','main','refs/heads/main','v1.2.3\nBAD=1','../x']:
   with self.subTest(tag=tag),self.assertRaises(ValueError):prepare.select_upstream(tag)
 def test_desktop_and_prerelease_updates_do_not_hide_stable_source(self):
  releases=[{'tag_name':'desktop-v9.0.0'}, {'tag_name':'v2.0.0','prerelease':True}, {'tag_name':'v1.0.8'}, {'tag_name':'v1.0.9'}, {'tag_name':'v3.0.0','draft':True}]
  with mock.patch.object(prepare,'github_json',return_value=releases):self.assertEqual(prepare.select_upstream(''),'v1.0.9')
 def test_manual_tag_must_be_published_stable(self):
  with mock.patch.object(prepare,'github_json',return_value={'tag_name':'v1.2.3','prerelease':True}):
   with self.assertRaisesRegex(RuntimeError,'published stable'):prepare.select_upstream('v1.2.3')
 def test_missing_browser_validation_stops_packaging(self):
  with tempfile.TemporaryDirectory() as directory:
   with self.assertRaisesRegex(RuntimeError,'validation report'):
    assembler.mobile_validation({'release_commit':'abc','core_version':'1-openwrt'},pathlib.Path(directory))
 def test_browser_validation_is_bound_to_source_and_version(self):
  with tempfile.TemporaryDirectory() as directory:
   out=pathlib.Path(directory);plan={'release_commit':'abc','core_version':'1-openwrt'}
   report={'commit':'other','core_version':'1-openwrt','viewports':[320,390,768,844,932,1280],'passed':True}
   (out/'mobile-check.json').write_text(json.dumps(report))
   with self.assertRaisesRegex(RuntimeError,'matching mobile-browser'):assembler.mobile_validation(plan,out)
   report['commit']='abc';(out/'mobile-check.json').write_text(json.dumps(report))
   self.assertTrue(assembler.mobile_validation(plan,out)['passed'])
 def test_publisher_rejects_checkout_change_before_any_upload(self):
  with mock.patch.object(publisher,'run',return_value='another-commit') as run:
   with self.assertRaisesRegex(RuntimeError,'changed after build'):
    publisher.publish({'release_tag':'openwrt-v1.0.0-r2','repository':'example/fork','release_commit':'expected'},pathlib.Path('/unused'))
   self.assertEqual(run.call_count,1)

if __name__=='__main__':unittest.main()
