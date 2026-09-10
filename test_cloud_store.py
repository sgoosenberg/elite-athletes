import io
import json
import os
import unittest
from unittest.mock import patch

import cloud_store
import portal
from hosted import application


class CloudStorageTests(unittest.TestCase):
    def test_pagination_does_not_drop_submissions(self):
        first = [{'id': str(index)} for index in range(500)]
        with patch.object(cloud_store, 'request', side_effect=[first, [{'id': 'last'}]]) as request:
            self.assertEqual(len(cloud_store.load_names()), 501)
            self.assertIn('offset=500', request.call_args.args[0])

    def test_updates_only_target_record(self):
        with patch.object(cloud_store, 'request') as request:
            cloud_store.save_entry({'id': 'one', 'name': 'Athlete', 'phone': '555', 'status': 'denied', 'created_at': 'old'})
            records = request.call_args.args[2]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]['status'], 'denied')
            self.assertNotIn('created_at', records[0])

    def test_private_video_upload_and_expiring_url(self):
        with patch.dict(os.environ, {'SUPABASE_URL': 'https://example.supabase.co', 'SUPABASE_SECRET_KEY': 'sb_secret_test'}):
            with patch.object(cloud_store, 'request', return_value={'signedURL': '/object/sign/highlights/a.mp4?token=example'}) as request:
                self.assertEqual(cloud_store.signed_video_url('a.mp4'), 'https://example.supabase.co/storage/v1/object/sign/highlights/a.mp4?token=example')
                self.assertEqual(request.call_args.args[2], {'expiresIn': 300})
            with patch.object(cloud_store, 'request') as request:
                cloud_store.save_video('a.mp4', b'video', 'video/mp4')
                self.assertEqual(request.call_args.args[0], '/storage/v1/object/highlights/a.mp4')
                self.assertEqual(request.call_args.args[3], 'video/mp4')

    def test_provider_error_does_not_become_empty_results(self):
        with patch.object(portal, 'CLOUD_STORAGE', True), patch.object(cloud_store, 'load_names', side_effect=cloud_store.StorageError('Unavailable')):
            with self.assertRaises(cloud_store.StorageError):
                portal.load_names()

    def test_cloud_submission_uses_no_local_file(self):
        from test_portal import ReviewWorkflowTests
        helper = ReviewWorkflowTests()
        rows = []
        with patch.object(portal, 'CLOUD_STORAGE', True), patch.object(cloud_store, 'load_names', side_effect=lambda: list(rows)), patch.object(cloud_store, 'save_entry', side_effect=lambda entry: rows.append(dict(entry))), patch.object(portal, 'save_names') as local_save:
            status, _ = helper.request(portal.PORTAL_PATH, {'name': 'Cloud Athlete', 'phone': '555'})
            self.assertEqual(status, 303)
            self.assertEqual(rows[0]['status'], 'pending')
            self.assertEqual(portal.load_names()[0]['name'], 'Cloud Athlete')
            local_save.assert_not_called()

    def test_server_secret_sent_only_to_provider(self):
        response = io.BytesIO(b'[]')
        with patch.dict(os.environ, {'SUPABASE_URL': 'https://example.supabase.co', 'SUPABASE_SECRET_KEY': 'sb_secret_test'}), patch.object(cloud_store, 'urlopen', return_value=response) as open_url:
            self.assertEqual(cloud_store.request('/rest/v1/athlete_submissions'), [])
            request = open_url.call_args.args[0]
            self.assertEqual(request.get_header('Apikey'), 'sb_secret_test')
            self.assertNotIn('sb_secret_test', request.full_url)


if __name__ == '__main__':
    unittest.main()
