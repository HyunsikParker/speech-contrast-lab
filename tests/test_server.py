import base64
from http.client import HTTPConnection
import json
from pathlib import Path
import stat
import threading
import unittest
from unittest.mock import patch

import server


class LocalServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.port = cls.http.server_address[1]
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown(); cls.http.server_close(); cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        connection = HTTPConnection('127.0.0.1', self.port, timeout=3)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_host_and_cross_origin_gate(self):
        self.assertEqual(self.request('GET', '/api/manifest', headers={'Host': 'attacker.invalid'})[0], 403)
        self.assertEqual(self.request('POST', '/api/compare', '{}', {'Origin': 'https://attacker.invalid', 'Content-Type': 'application/json'})[0], 403)

    def test_static_traversal_and_unknown_example(self):
        self.assertEqual(self.request('GET', '/%2e%2e/%2e%2e/data/portfolio.json')[0], 404)
        self.assertEqual(self.request('GET', '/api/analysis/no-such-example')[0], 404)

    def test_audio_byte_ranges_support_real_seeking(self):
        example = server.load_manifest()['examples'][0]
        status, headers, body = self.request('GET', f"/api/audio/{example['id']}/delivery", headers={'Range': 'bytes=0-9'})
        self.assertEqual(status, 206)
        self.assertEqual(body, (server.ROOT / example['audio']).read_bytes()[:10])
        self.assertEqual(headers['Accept-Ranges'], 'bytes')

    def test_request_limits_and_invalid_audio(self):
        self.assertEqual(self.request('POST', '/api/compare', '{}', {'Content-Length': str(server.MAX_BODY + 1), 'Content-Type': 'application/json'})[0], 413)
        invalid = {'transcript': 'SAME TEXT', 'reference': {'extension': 'wav', 'data': '%%%invalid'}, 'delivery': {'extension': 'wav', 'data': 'A==='}}
        self.assertEqual(self.request('POST', '/api/compare', json.dumps(invalid), {'Content-Type': 'application/json'})[0], 400)

    def test_temporary_uploads_are_private_and_deleted_even_for_abstention(self):
        observed = {}
        def child(argv, **kwargs):
            request_path, result_path = map(Path, argv[-2:])
            observed['folder'] = request_path.parent
            payload = json.loads(request_path.read_text())
            self.assertEqual(stat.S_IMODE(request_path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(request_path.parent.stat().st_mode), 0o700)
            for name in ['reference', 'delivery']:
                self.assertEqual(stat.S_IMODE(Path(payload[name]).stat().st_mode), 0o600)
            self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
            self.assertEqual(kwargs['env']['HF_HUB_OFFLINE'], '1')
            result_path.write_text(json.dumps({'abstained': True, 'score': None, 'regions': []}))
            return type('Process', (), {'returncode': 0})()
        upload = {'extension': 'wav', 'data': base64.b64encode(b'synthetic-privacy-test').decode()}
        with patch('server.subprocess.run', side_effect=child):
            status, _, body = self.request('POST', '/api/compare', json.dumps({'reference': upload, 'delivery': upload, 'transcript': 'SAME TEXT'}), {'Content-Type': 'application/json'})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)['abstained'])
        self.assertFalse(observed['folder'].exists())

    def test_comparisons_are_serialized_without_queueing_uploads(self):
        server.ANALYSIS_LOCK.acquire()
        try:
            self.assertEqual(self.request('POST', '/api/compare', '{}', {'Content-Type': 'application/json'})[0], 503)
        finally:
            server.ANALYSIS_LOCK.release()


if __name__ == '__main__':
    unittest.main()
