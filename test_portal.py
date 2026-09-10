import io
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

import portal


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for name, value in [('DATA_FILE', root / 'names.json'), ('EXPORT_DIR', root / 'exports'), ('UPLOAD_DIR', root / 'uploads')]:
            patcher = patch.object(portal, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def request(self, path, form=None, content_type=None, client="127.0.0.1", authorization=None):
        handler = object.__new__(portal.PortalHandler)
        handler.path = path
        handler.client_address = (client, 12345)
        if isinstance(form, dict) and path == portal.BACKEND_PATH:
            form = {'csrf': portal.CSRF_TOKEN, **form}
        body = form if isinstance(form, bytes) else urlencode(form or {}).encode()
        handler.headers = {'Content-Length': str(len(body))}
        if content_type:
            handler.headers['Content-Type'] = content_type
        if authorization:
            handler.headers["Authorization"] = authorization
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        handler.send_response = lambda status: setattr(handler, 'status', status)
        handler.send_header = lambda *args: None
        handler.end_headers = lambda: None
        handler.send_error = lambda status, *args: setattr(handler, 'status', status)
        if form is None:
            handler.do_GET()
        else:
            handler.do_POST()
        return handler.status, handler.wfile.getvalue().decode()

    def test_submission_approval_denial_and_reapproval(self):
        status, _ = self.request(portal.PORTAL_PATH, {'name': 'Test Athlete', 'phone': '555-0199', 'history': '<captain>\nVarsity'})
        self.assertEqual(status, 303)
        entry = portal.load_names()[0]
        self.assertEqual(entry['status'], 'pending')
        self.assertNotIn('Test Athlete', self.request(portal.PORTAL_PATH)[1])
        backend = self.request(portal.BACKEND_PATH)[1]
        self.assertIn('Test Athlete', backend)
        self.assertIn('555-0199', backend)
        self.assertIn('&lt;captain&gt;', backend)
        for decision in ['approved', 'denied', 'approved']:
            status, _ = self.request(portal.BACKEND_PATH, {'id': entry['id'], 'decision': decision})
            self.assertEqual(status, 303)
            self.assertEqual(portal.load_names()[0]['status'], decision)
            public = self.request(portal.PORTAL_PATH)[1]
            self.assertNotIn('Test Athlete', public)
            self.assertNotIn('555-0199', public)
            self.assertNotIn('&lt;captain&gt;', public)
            self.assertIn(decision, (portal.EXPORT_DIR / 'athletes.json').read_text())
        self.assertEqual(len(portal.load_names()), 1)

    def test_existing_entries_remain_approved_and_can_be_denied(self):
        portal.DATA_FILE.write_text('[{"name":"Existing Athlete","phone":"555"}, "Older Athlete"]')
        self.assertNotIn('Existing Athlete', self.request(portal.PORTAL_PATH)[1])
        entry = portal.load_names()[0]
        self.request(portal.BACKEND_PATH, {'id': entry['id'], 'decision': 'denied'})
        self.assertNotIn('Existing Athlete', self.request(portal.PORTAL_PATH)[1])
        self.assertNotIn('Older Athlete', self.request(portal.PORTAL_PATH)[1])
        denied = self.request(portal.BACKEND_PATH)[1].split('<h2>Denied submissions')[1]
        self.assertIn('Existing Athlete', denied)

    def test_highlights_link_and_video_upload(self):
        boundary = 'test-boundary'
        body = b''
        for name, value in [('name', 'Video Athlete'), ('phone', '555'), ('highlights_url', 'https://example.com/highlights')]:
            body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode()
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="highlights_video"; filename="clip.mp4"\r\nContent-Type: video/mp4\r\n\r\n').encode()
        payload = b'\x00\x00\x00\x18ftypisom' + b'example video bytes'
        body += payload + f'\r\n--{boundary}--\r\n'.encode()
        status, _ = self.request(portal.PORTAL_PATH, body, f'multipart/form-data; boundary={boundary}')
        self.assertEqual(status, 303)
        entry = portal.load_names()[0]
        self.assertEqual((portal.UPLOAD_DIR / entry['highlights_video']).read_bytes(), payload)
        backend = self.request(portal.BACKEND_PATH)[1]
        self.assertIn('https://example.com/highlights', backend)
        self.assertIn('/highlights/' + entry['highlights_video'], backend)
        self.assertIn('<video controls', backend)
        self.assertNotIn('example.com/highlights', self.request(portal.PORTAL_PATH)[1])
        self.assertEqual(self.request('/highlights/../../names.json')[0], 404)
        bad = body.replace(b'ftyp', b'xxxx')
        self.assertEqual(self.request(portal.PORTAL_PATH, bad, f'multipart/form-data; boundary={boundary}')[0], 400)
        self.assertEqual(len(portal.load_names()), 1)

    def test_invalid_highlights_link(self):
        status, _ = self.request(portal.PORTAL_PATH, {'name': 'Test', 'phone': '555', 'highlights_url': 'javascript:alert(1)'})
        self.assertEqual(status, 400)
        self.assertEqual(portal.load_names(), [])

    def test_wifi_access_keeps_backend_and_videos_local(self):
        self.assertEqual(self.request(portal.PORTAL_PATH, client="10.0.0.99")[0], 200)
        self.assertEqual(self.request(portal.PORTAL_PATH, {'name': 'Phone Athlete', 'phone': '555'}, client="10.0.0.99")[0], 303)
        entry = portal.load_names()[0]
        self.assertEqual(self.request(portal.BACKEND_PATH, client="10.0.0.99")[0], 403)
        self.assertEqual(self.request(portal.BACKEND_PATH, {'id': entry['id'], 'decision': 'approved'}, client="10.0.0.99")[0], 403)
        self.assertEqual(self.request('/highlights/' + 'a' * 32 + '.mp4', client="10.0.0.99")[0], 403)
        self.assertEqual(portal.load_names()[0]['status'], 'pending')
        self.assertEqual(self.request(portal.BACKEND_PATH)[0], 200)

    def test_public_only_blocks_backend_even_through_local_proxy(self):
        with patch.object(portal, 'PUBLIC_ONLY', True):
            self.assertEqual(self.request(portal.PORTAL_PATH)[0], 200)
            self.assertEqual(self.request(portal.BACKEND_PATH)[0], 403)
            self.assertEqual(self.request(portal.BACKEND_PATH, {'id': 'any', 'decision': 'approved'})[0], 403)
            self.assertEqual(self.request('/highlights/' + 'a' * 32 + '.mp4')[0], 403)

    def test_hosted_backend_is_disabled_even_with_password(self):
        with patch.object(portal, 'HOSTED', True):
            self.assertEqual(self.request(portal.BACKEND_PATH)[0], 403)
            self.assertEqual(self.request(portal.BACKEND_PATH, authorization='Basic anything')[0], 403)

    def test_review_requires_csrf(self):
        self.request(portal.PORTAL_PATH, {'name': 'Test', 'phone': '555'})
        entry = portal.load_names()[0]
        status, _ = self.request(portal.BACKEND_PATH, {'id': entry['id'], 'decision': 'approved', 'csrf': ''})
        self.assertEqual(status, 403)
        self.assertEqual(portal.load_names()[0]['status'], 'pending')

    def test_invalid_routes_and_decisions_do_not_change_records(self):
        self.request(portal.PORTAL_PATH, {'name': 'Test', 'phone': '555'})
        before = portal.DATA_FILE.read_text()
        self.assertEqual(self.request('/missing')[0], 404)
        self.assertEqual(self.request('/missing', {'name': 'Other', 'phone': '555'})[0], 404)
        self.assertEqual(self.request(portal.BACKEND_PATH, {'id': 'missing', 'decision': 'approved'})[0], 404)
        self.assertEqual(self.request(portal.BACKEND_PATH, {'id': portal.load_names()[0]['id'], 'decision': 'invalid'})[0], 400)
        self.assertEqual(portal.DATA_FILE.read_text(), before)


if __name__ == '__main__':
    unittest.main()
