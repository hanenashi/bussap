"""The public listener must not leak BUSSAP data before authentication."""

import importlib.util
import secrets
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


@unittest.skipUnless(importlib.util.find_spec("fido2"), "gateway dependency is not installed")
class PublicGatewayTests(unittest.TestCase):
    def setUp(self):
        import public_gateway

        self.gateway = public_gateway
        self.temporary = tempfile.TemporaryDirectory()
        db_path = Path(self.temporary.name) / "auth.sqlite3"
        public_gateway.init_db(db_path)
        public_gateway.GatewayHandler.db_path = db_path
        public_gateway.GatewayHandler.allowed_origins = frozenset({"http://localhost"})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), public_gateway.GatewayHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def status(self, path):
        try:
            with urlopen(self.base + path, timeout=3) as response:
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()

    def test_unregistered_visitor_cannot_read_data_or_pdf(self):
        status, body = self.status("/")
        self.assertEqual(status, 200)
        self.assertIn(b"/auth.js", body)
        for path in ("/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png"):
            self.assertEqual(self.status(path)[0], 200, path)
        for path in ("/health", "/api/stops?operator=chuo&name=x", "/app.js", "/sw.js"):
            self.assertEqual(self.status(path)[0], 401, path)
        for path in ("/network-map", "/network-map.js", "/network-map.pdf"):
            self.assertEqual(self.status(path)[0], 404, path)

    def test_authenticated_visitor_can_open_pdf(self):
        token = secrets.token_urlsafe(32)
        with self.gateway.connect(self.gateway.GatewayHandler.db_path) as db:
            db.execute("INSERT INTO sessions VALUES (?, ?, ?)",
                       (self.gateway.sha(token), "test", int(time.time()) + 60))
        for path in ("/", "/network-map", "/network-map.js", "/network-map.pdf"):
            request = Request(self.base + path, headers={"Cookie": f"bussap_session={token}"})
            with urlopen(request, timeout=5) as response:
                body = response.read()
                self.assertEqual(response.status, 200, path)
                if path == "/":
                    self.assertIn(b"/network-map", body)
                if path == "/network-map.pdf":
                    self.assertTrue(body.startswith(b"%PDF-"))

    def test_cross_origin_post_is_denied(self):
        request = Request(self.base + "/auth/login/begin", data=b"{}", headers={"Origin": "https://elsewhere.example"})
        with self.assertRaises(HTTPError) as result:
            urlopen(request, timeout=3)
        self.assertEqual(result.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
