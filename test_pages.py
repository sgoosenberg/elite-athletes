import io
import unittest
from pathlib import Path
from unittest.mock import patch
import hosted
import portal
import build_pages


class PagesTests(unittest.TestCase):
    def test_retired_host_never_serves_admin_or_data(self):
        for path in ('/', '/elite-athletes', '/elite-athletes-backend', '/highlights/a.mp4'):
            for method in ('GET', 'POST'):
                statuses = []
                body = hosted.application({'PATH_INFO': path, 'REQUEST_METHOD': method}, lambda status, headers: statuses.append(status))
                self.assertEqual(statuses, ['410 Gone'])
                self.assertEqual(body, [b'This service has been retired.'])

    def test_public_build_does_not_load_private_records(self):
        with patch.object(portal, 'load_names', side_effect=AssertionError('Private read')):
            build_pages.build()
        page = Path('docs/index.html').read_text()
        for private in ('Roster', 'elite-athletes-backend', 'csrf', 'SUPABASE_SECRET_KEY'):
            self.assertNotIn(private, page)
        self.assertIn('name="phone"', page)
        self.assertNotIn('Private Athlete', portal.render_page([{'name': 'Private Athlete', 'status': 'approved'}]))

    def test_server_refuses_network_configuration(self):
        with patch.dict(portal.os.environ, {'ELITE_ATHLETES_HOST': '0.0.0.0'}):
            with self.assertRaises(SystemExit):
                portal.main()

    def test_deployment_contains_static_frontend_only(self):
        config = Path('render.yaml').read_text()
        self.assertIn('staticPublishPath: ./docs', config)
        self.assertNotIn('gunicorn', config)
        self.assertNotIn('SUPABASE_SECRET_KEY', config)
