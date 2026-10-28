import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import update
import build_package

ROOT=Path(__file__).resolve().parents[1]


def entry(data):return {'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for name,data in {'VERSION':b'0.1\n','a.txt':b'old','b.txt':b'same','gone.txt':b'bye','.local/user.json':b'{"keep":1}'}.items():
            (self.root/name).parent.mkdir(parents=True,exist_ok=True);(self.root/name).write_bytes(data)
        (self.root/'MANIFEST.json').write_text(json.dumps({'version':'0.1','files':{'a.txt':entry(b'old'),'b.txt':entry(b'same'),'gone.txt':entry(b'bye')}}))
        self.remote={'VERSION':b'0.2\n','a.txt':b'new','b.txt':b'same','dir/c.txt':b'added','.gitignore':b'*.zip\n'}
        self.manifest={'version':'0.2','notes':'Mới','files':{k:entry(v) for k,v in self.remote.items()}}
        self.fetched=[]
        def fetch(name,limit=0):
            self.fetched.append(name)
            return json.dumps(self.manifest).encode() if name=='MANIFEST.json' else self.remote[name]
        self.patches=[mock.patch.object(update,'ROOT',self.root),mock.patch.object(update,'WORK',self.root/'.local'/'update'),mock.patch.object(update,'fetch',side_effect=fetch)]
        for p in self.patches:p.start()

    def tearDown(self):
        for p in self.patches:p.stop()
        self.tmp.cleanup()

    def test_only_changed_files_are_downloaded_and_old_ones_backed_up(self):
        plan=update.check()
        self.assertEqual((plan['current'],plan['latest'],plan['newer']),('0.1','0.2',True))
        self.assertEqual(plan['changed'],['.gitignore','VERSION','a.txt','dir/c.txt']);self.assertEqual(plan['removed'],['gone.txt'])
        result=update.apply(plan,log=lambda line:None)
        self.assertNotIn('b.txt',self.fetched)
        self.assertEqual(((self.root/'a.txt').read_bytes(),(self.root/'dir/c.txt').read_bytes()),(b'new',b'added'))
        self.assertFalse((self.root/'gone.txt').exists());self.assertEqual((self.root/'.local/user.json').read_bytes(),b'{"keep":1}')
        backup=Path(result['backup']);self.assertEqual(((backup/'a.txt').read_bytes(),(backup/'gone.txt').read_bytes()),(b'old',b'bye'))
        self.assertEqual(json.loads((self.root/'MANIFEST.json').read_text())['version'],'0.2')
        again=update.check();self.assertEqual((again['changed'],again['removed']),([],[]))

    def test_corrupt_download_changes_nothing(self):
        self.remote['a.txt']=b'tampered'
        with self.assertRaises(update.UpdateError):update.apply(log=lambda line:None)
        self.assertEqual((self.root/'a.txt').read_bytes(),b'old');self.assertTrue((self.root/'gone.txt').exists())

    def test_unsafe_paths_are_rejected(self):
        for bad in ('../evil.py','.local/x','.git/config','/etc/passwd','a\\b.py','dir/../x','..','dir/./x'):
            self.manifest['files']={bad:entry(b'x')}
            with self.assertRaises(update.UpdateError,msg=bad):update.check()

    def test_downloads_are_pinned_to_the_newest_commit(self):
        sha='ab'*20
        class Reply:
            def __init__(self,body):self.body=body
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,n=-1):return self.body
        with mock.patch.object(update,'SOURCE',''),mock.patch.dict(update._pinned,clear=True),mock.patch.object(update.request,'urlopen',return_value=Reply(sha.encode())):
            self.assertEqual(update.source(),f'https://raw.githubusercontent.com/{update.REPO}/{sha}/')
        # GitHub API unreachable → branch name, still works
        with mock.patch.object(update,'SOURCE',''),mock.patch.dict(update._pinned,clear=True),mock.patch.object(update.request,'urlopen',side_effect=update.error.URLError('x')):
            self.assertEqual(update.source(),f'https://raw.githubusercontent.com/{update.REPO}/{update.BRANCH}/')

    def test_each_check_looks_up_the_newest_commit_again(self):
        # a long-running app must see a release published after it started
        update._pinned['base']='https://raw.githubusercontent.com/x/y/'+'0'*40+'/'
        update.check();self.assertNotIn('base',update._pinned)

    def test_stale_cache_with_a_bigger_file_asks_to_retry(self):
        real=update.fetch.side_effect
        def fetch(name,limit=0):
            if name=='a.txt':raise update.UpdateError('a.txt lớn bất thường; dừng cập nhật.')
            return real(name,limit)
        update.fetch.side_effect=fetch
        with self.assertRaisesRegex(update.UpdateError,'Chạy lại'):update.apply(log=lambda line:None)
        self.assertEqual((self.root/'a.txt').read_bytes(),b'old')

    def test_version_order(self):
        self.assertGreater(update.version_key('0.12.1'),update.version_key('0.12'))
        self.assertGreater(update.version_key('0.13'),update.version_key('0.12.9'))


class ManifestTests(unittest.TestCase):
    def test_published_manifest_matches_the_files(self):
        """Run `python build_package.py --manifest` before committing a release."""
        manifest=json.loads((ROOT/'MANIFEST.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['version'],(ROOT/'VERSION').read_text(encoding='utf-8').strip())
        expected={n for n in build_package.FILES if n!='MANIFEST.json'}
        self.assertEqual(set(manifest['files']),expected)
        for name,info in manifest['files'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),info['sha256'],name+' changed: run python build_package.py --manifest')


if __name__=='__main__':
    unittest.main()
