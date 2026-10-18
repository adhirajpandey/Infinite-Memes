import concurrent.futures
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener

import requests

import app as application


class AppTests(unittest.TestCase):
    def setUp(self):
        self.client = application.app.test_client()
        warning = patch.object(application.app.logger, "warning")
        warning.start()
        self.addCleanup(warning.stop)

    def response(self, payload):
        response = MagicMock()
        response.__enter__.return_value = response
        response.json.return_value = payload
        return response

    @patch("app.requests.get")
    def test_success(self, get):
        get.return_value = self.response(
            {"subreddit": "memes", "preview": ["https://example.test/meme.jpg"]}
        )
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"https://example.test/meme.jpg", response.data)
        get.assert_called_once()
        self.assertEqual(
            get.call_args.kwargs, {"timeout": (2, 3), "allow_redirects": False}
        )

    @patch("app.requests.get")
    def test_network_failures_do_not_retry(self, get):
        for error in (
            requests.ConnectTimeout(),
            requests.ReadTimeout(),
            requests.ConnectionError(),
        ):
            with self.subTest(error=type(error).__name__):
                get.reset_mock()
                get.side_effect = error
                response = self.client.get("/")
                self.assertEqual(response.status_code, 503)
                self.assertIn(b"Memes are temporarily unavailable", response.data)
                self.assertNotIn(b'<img src=""', response.data)
                get.assert_called_once()

    @patch("app.requests.get")
    def test_http_failure_does_not_retry(self, get):
        upstream = self.response({})
        upstream.raise_for_status.side_effect = requests.HTTPError()
        get.return_value = upstream
        self.assertEqual(self.client.get("/").status_code, 503)
        get.assert_called_once()
        upstream.json.assert_not_called()

    @patch("app.requests.get")
    def test_invalid_payload_does_not_retry(self, get):
        for payload in (
            {},
            None,
            [],
            {"subreddit": "memes", "preview": []},
            {"subreddit": "memes", "preview": "wrong"},
            {"subreddit": None, "preview": ["https://example.test/a"]},
            {"subreddit": "memes", "preview": [None]},
        ):
            with self.subTest(payload=payload):
                get.reset_mock()
                get.return_value = self.response(payload)
                self.assertEqual(self.client.get("/").status_code, 503)
                get.assert_called_once()

    @patch("app.requests.get")
    def test_invalid_json(self, get):
        upstream = self.response(None)
        upstream.json.side_effect = ValueError("invalid JSON")
        get.return_value = upstream
        self.assertEqual(self.client.get("/").status_code, 503)
        get.assert_called_once()

    @patch(
        "app.requests.get", side_effect=AssertionError("unexpected upstream request")
    )
    def test_health_does_not_use_upstream(self, get):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})
        get.assert_not_called()


class GunicornTests(unittest.TestCase):
    def test_health_responds_while_upstream_stalls(self):
        started = threading.Event()
        release = threading.Event()
        calls = []

        class StalledAPI(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append(self.path)
                started.set()
                release.wait(10)
                self.close_connection = True

            def log_message(self, *args):
                pass

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), StalledAPI)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        # Select a free loopback port for the temporary application process.
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        opener = build_opener(ProxyHandler({}))

        def request(path):
            try:
                with opener.open(base + path, timeout=6) as response:
                    return response.status, response.read()
            except HTTPError as error:
                with error:
                    return error.code, error.read()

        root = Path(__file__).resolve().parents[1]
        try:
            with tempfile.TemporaryDirectory() as directory:
                # Override only the upstream address, retaining real Requests I/O.
                Path(directory, "stalled_app.py").write_text(
                    "import app as application\n"
                    f"application.MEME_API_URL = 'http://127.0.0.1:{upstream.server_port}/'\n"
                    "app = application.app\n"
                )
                environment = dict(os.environ)
                environment.pop("GUNICORN_CMD_ARGS", None)
                environment.pop("WEB_CONCURRENCY", None)
                environment["PYTHONPATH"] = os.pathsep.join((str(root), directory))
                with tempfile.TemporaryFile() as logs:
                    process = subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "gunicorn",
                            "--config",
                            "gunicorn.conf.py",
                            "--bind",
                            f"127.0.0.1:{port}",
                            "stalled_app:app",
                        ],
                        cwd=root,
                        env=environment,
                        stdout=logs,
                        stderr=logs,
                    )
                    try:
                        deadline = time.monotonic() + 10
                        while True:
                            if process.poll() is not None:
                                logs.seek(0)
                                self.fail(logs.read().decode())
                            try:
                                status, _ = request("/health")
                                if status == 200:
                                    break
                            except OSError:
                                pass
                            if time.monotonic() >= deadline:
                                self.fail("Gunicorn did not start")
                            time.sleep(0.05)

                        with concurrent.futures.ThreadPoolExecutor(
                            max_workers=1
                        ) as pool:
                            begin = time.monotonic()
                            homepage = pool.submit(request, "/")
                            self.assertTrue(started.wait(2), "Upstream was not called")
                            health_begin = time.monotonic()
                            status, body = request("/health")
                            self.assertEqual(status, 200)
                            self.assertEqual(json.loads(body), {"status": "ok"})
                            self.assertLess(time.monotonic() - health_begin, 1)
                            self.assertFalse(
                                homepage.done(), "Upstream should still be stalled"
                            )
                            status, body = homepage.result(timeout=5)
                            self.assertEqual(status, 503)
                            self.assertIn(b"Memes are temporarily unavailable", body)
                            self.assertLess(time.monotonic() - begin, 5)
                            self.assertEqual(len(calls), 1)
                            self.assertEqual(request("/health")[0], 200)
                    finally:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
        finally:
            release.set()
            upstream.shutdown()
            upstream.server_close()
            upstream_thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
