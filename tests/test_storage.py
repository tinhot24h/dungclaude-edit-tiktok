import http.client
import json
import os
import shutil
import sys
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

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg required')
    def test_hardware_failure_falls_back_to_cpu(self):
        key='9'*32;self.project(key)
        broken=[sys.executable,'-c','raise SystemExit(3)']
        working=['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=s=72x128:r=30:d=0.5','-c:v','libx264','-pix_fmt','yuv420p','review.mp4']
        app.render(key,broken,dict(width=72,height=128,duration=.5,encoder='h264_nvenc'),'gpu',None,working)
        job=app.JOBS.pop(key)
        self.assertEqual((job['state'],job['encoder']),('done','cpu'),job)

    def test_project_and_template_library(self):
        status,data=self.call('POST','/library/projects/save',json.dumps({'name':'  Dự án   A ','data':{'video_id':'a'*32,'design':{'color':'#ffffff'}}}).encode())
        self.assertEqual(status,200);saved=json.loads(data)
        self.assertEqual(saved['name'],'Dự án A')
        status,data=self.call('POST','/library/projects/save',json.dumps({'id':saved['id'],'name':'Dự án B','data':{}}).encode())
        status,data=self.call('GET','/library/projects')
        self.assertEqual([(i['id'],i['name']) for i in json.loads(data)['items']],[(saved['id'],'Dự án B')])
        status,data=self.call('GET','/library/projects/'+saved['id'])
        self.assertEqual((status,json.loads(data)['data']),(200,{}))
        self.assertEqual(json.loads(self.call('GET','/library/templates')[1])['items'],[])
        for body in (b'[]',b'{"name":"","data":{}}',b'{"name":"x","data":[]}',json.dumps({'id':'../x','name':'x','data':{}}).encode()):
            self.assertEqual(self.call('POST','/library/templates/save',body)[0],400)
        self.assertEqual(self.call('POST',f"/library/projects/{saved['id']}/delete")[0],200)
        self.assertEqual(self.call('GET','/library/projects/'+saved['id'])[0],404)

    def test_video_library_lists_uploaded_sources(self):
        key='7'*32;folder=self.project(key)
        (folder/'source.json').write_text(json.dumps({'id':key,'name':'clip.mp4','duration':3}),encoding='utf-8')
        self.project('6'*32)
        rows=json.loads(self.call('GET','/media/videos')[1])['videos']
        self.assertEqual([(r['id'],r['thumb']) for r in rows],[(key,'/media/thumb/'+key)])

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
