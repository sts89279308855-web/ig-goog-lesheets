import datetime as dt,json,unittest
from unittest.mock import Mock,patch
import cloud_pipeline as p

class PublicationSafety(unittest.TestCase):
 def setUp(self):
  self.entry={'id':'test','status':'ready','date':'2026-10-31','caption':'A unique teaching example','video_raw_url':'https://example.invalid/test.mp4'}
  self.media={'id':'123','caption':self.entry['caption'],'timestamp':'2026-10-31T15:40:05+0000','permalink':'https://example.invalid/post'}
  self.client=Mock()
  self.patches=[patch.object(p,'connection',return_value=self.client),patch.object(p,'queue',return_value=[self.entry]),patch.object(p,'now',return_value=dt.datetime(2026,10,31,20,40,tzinfo=p.TZ)),patch.object(p,'read_file',return_value=(None,None)),patch.object(p,'save_json'),patch.object(p,'status'),patch.object(p,'finish'),patch.object(p.time,'sleep')]
  for item in self.patches:item.start();self.addCleanup(item.stop)
 def test_already_posted_today_never_creates_container(self):
  with patch.object(p,'recent',return_value=[dict(self.media,caption='Another post')]):p.publish()
  self.client.tool.assert_not_called()
 def test_uncertain_response_is_reconciled_without_second_publish(self):
  def execute(name,args):
   if name=='INSTAGRAM_POST_IG_USER_MEDIA':return {'id':'container'}
   if name=='INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH':raise TimeoutError('Simulated response loss')
   raise AssertionError('Unexpected provider action')
  self.client.tool.side_effect=execute
  with patch.object(p,'recent',side_effect=[[],[self.media]]):p.publish()
  self.assertEqual(sum(c.args[0]=='INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH' for c in self.client.tool.call_args_list),1)
  p.finish.assert_called_once_with(self.entry,self.media)
 def test_unknown_response_stops_and_preserves_unknown_attempt(self):
  self.client.tool.side_effect=[{'id':'container'},TimeoutError('Simulated response loss')]
  with patch.object(p,'recent',return_value=[]):
   with self.assertRaisesRegex(RuntimeError,'Uncertain'):p.publish()
  self.assertEqual(p.save_json.call_args.args[1]['status'],'unknown')
  self.assertEqual(self.client.tool.call_count,2)
 def test_existing_ambiguous_attempt_is_not_sent_again(self):
  with patch.object(p,'recent',return_value=[]),patch.object(p,'read_file',return_value=(json.dumps({'status':'publishing'}),'sha')):
   with self.assertRaisesRegex(RuntimeError,'no blind retry'):p.publish()
  self.client.tool.assert_not_called()
 def test_outside_window_never_posts(self):
  with patch.object(p,'recent',return_value=[]),patch.object(p,'now',return_value=dt.datetime(2026,10,31,12,0,tzinfo=p.TZ)):
   with self.assertRaisesRegex(RuntimeError,'Outside'):p.publish()
  self.client.tool.assert_not_called()
 def test_planned_video_never_posts(self):
  with patch.object(p,'recent',return_value=[]),patch.object(p,'queue',return_value=[dict(self.entry,status='planned')]):
   with self.assertRaisesRegex(RuntimeError,'No ready'):p.publish()
  self.client.tool.assert_not_called()
 def test_incomplete_media_response_cannot_be_treated_as_empty_account(self):
  self.client.tool.return_value={}
  with self.assertRaisesRegex(RuntimeError,'Incomplete'):p.recent(self.client)

if __name__=='__main__':unittest.main()
