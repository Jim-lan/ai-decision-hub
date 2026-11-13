"""C-001 local entrypoint checks without Docker or real credentials."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class LocalBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        scripts = self.root / "infra/scripts"
        scripts.mkdir(parents=True)
        source = Path(__file__).resolve().parents[1] / "scripts"
        for name in ("start-local.sh", "init-local.sh"):
            shutil.copy(source / name, scripts / name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        docker = self.bin / "docker"
        docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" > docker-invoked\n')
        docker.chmod(0o700)

    def run_script(self, name):
        return subprocess.run(
            ["sh", str(self.root / "infra/scripts" / name)],
            env=os.environ | {"PATH": str(self.bin) + os.pathsep + os.environ["PATH"]},
            text=True, capture_output=True, check=False,
        )

    def test_missing_bootstrap_fails_before_docker(self):
        result = self.run_script("start-local.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("infra/scripts/init-local.sh", result.stderr)
        self.assertFalse((self.root / "docker-invoked").exists())

    def test_empty_bootstrap_fails_without_revealing_other_secret(self):
        secrets = self.root / ".secrets"
        secrets.mkdir()
        (secrets / "db_password").write_text("synthetic-private-marker")
        (secrets / "owner_password").touch()
        result = self.run_script("start-local.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("synthetic-private-marker", result.stdout + result.stderr)
        self.assertFalse((self.root / "docker-invoked").exists())

    def test_initialized_bootstrap_starts_expected_services(self):
        self.assertEqual(self.run_script("init-local.sh").returncode, 0)
        self.assertTrue((self.root / ".secrets/cursor_signing_key").stat().st_size >= 48)
        result = self.run_script("start-local.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "docker-invoked").read_text().strip(),
                         "compose up -d --build --wait web")

    def test_initializer_preserves_credentials(self):
        self.assertEqual(self.run_script("init-local.sh").returncode, 0)
        paths = list((self.root / ".secrets").iterdir())
        before = {path.name: path.read_bytes() for path in paths}
        self.assertEqual(self.run_script("init-local.sh").returncode, 0)
        self.assertEqual(before, {path.name: path.read_bytes() for path in paths})
        self.assertTrue(all(path.stat().st_mode & 0o077 == 0 for path in paths))

    def test_proxy_access_log_excludes_sensitive_query_string(self):
        config = (Path(__file__).resolve().parents[2] / "apps/web/nginx.conf").read_text()
        log_format = config.split("server {", 1)[0]
        self.assertIn("log_format query_safe", log_format)
        self.assertIn("access_log /var/log/nginx/access.log query_safe", config)
        self.assertIn("$request_method $uri $server_protocol", log_format)
        self.assertNotIn("$request ", log_format)
        self.assertNotIn("$args", log_format)
        self.assertNotIn("$request_uri", log_format)
        self.assertNotIn("$http_referer", log_format)


if __name__ == "__main__":
    unittest.main()
