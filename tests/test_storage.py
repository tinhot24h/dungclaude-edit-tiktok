import http.client
import json
import os
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
import app


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'audio').mkdir();(self.root/'frames').mkdir()
        self.patches=[patch.object(app,'DATA',self.root),patch.object(app,'AUDIO',self.root/'audio'),patch.object(app,'FRAMES',self.root/'frames')]
        for item in self.patches:item.start()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close()
        for item in self.patches:item.stop()
        self.tmp.cleanup()

    def call(self,method,path,body=b'',headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=30)
        conn.request(method,path,body=body,headers=headers or {})
        response=conn.getresponse();data=response.read();conn.close()
        return response.status,data

    def project(self,key,age_days=0):
        folder=self.root/key;folder.mkdir()
        (folder/'source').write_bytes(b'x'*1000)
        old=time.time()-age_days*86400
        for item in [folder/'source',folder]:os.utime(item,(old,old))
        return folder

    def test_rejected_upload_leaves_no_folder(self):
        status,_=self.call('POST','/upload',b'not a video at all',{'X-Filename':'clip.mp4'})
        self.assertEqual(status,400)
        self.assertEqual(app.projects(),[])

    def test_finished_job_survives_restart(self):
        key='b'*32;folder=self.project(key)
        (folder/'review.mp4').write_bytes(b'video-bytes')
        app.save_job(key,{'state':'done','progress':100,'url':'/download/'+key,'name':'Phim thử'})
        app.JOBS.pop(key,None)
        status,data=self.call('GET','/jobs/'+key)
        self.assertEqual((status,json.loads(data)['state']),(200,'done'))
        status,data=self.call('GET','/download/'+key)
        self.assertEqual((status,data),(200,b'video-bytes'))

    def test_cleanup_removes_only_idle_projects_and_stale_temp(self):
        old,fresh,busy='c'*32,'d'*32,'e'*32
        self.project(old,40);self.project(fresh,1);self.project(busy,40)
        app.JOBS[busy]={'state':'rendering'}
        (self.root/'audio'/('f'*32+'.mp3')).write_bytes(b'mp3')
        stale=self.root/'audio'/'x.input';stale.write_bytes(b'tmp');os.utime(stale,(0,0))
        try:
            result=app.cleanup(30)
        finally:app.JOBS.pop(busy,None)
        self.assertEqual(result['removed'],1)
        self.assertEqual(sorted(p.name for p in app.projects()),[fresh,busy])
        self.assertTrue((self.root/'audio'/('f'*32+'.mp3')).is_file())
        self.assertFalse(stale.exists())

    def test_cleanup_endpoint_validates_days(self):
        for days in (0,'7',True):
            status,_=self.call('POST','/storage/cleanup',json.dumps({'days':days}).encode())
            self.assertEqual(status,400)
        status,data=self.call('POST','/storage/cleanup',b'{"days":7}')
        self.assertEqual(status,200);self.assertIn('project_bytes',json.loads(data))

    def test_delete_audio(self):
        aid='a'*32
        (self.root/'audio'/(aid+'.mp3')).write_bytes(b'mp3');(self.root/'audio'/(aid+'.json')).write_text('{}')
        status,_=self.call('POST',f'/audio/{aid}/delete')
        self.assertEqual(status,200)
        self.assertEqual(list((self.root/'audio').iterdir()),[])
        status,_=self.call('POST',f'/audio/{aid}/delete')
        self.assertEqual(status,400)


if __name__=='__main__':
    unittest.main()
