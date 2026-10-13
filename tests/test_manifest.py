import json, os, subprocess, tempfile, unittest
from pathlib import Path
from agentvow import manifest, pack


def mkrepo(d):
    r = Path(d) / "r"; (r / "tests").mkdir(parents=True)
    g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
    g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
    (r / ".gitignore").write_text(".venv/\n.agentvow/\nlocal_data/\n*.sqlite\n__pycache__/\n")
    (r / "app.py").write_text("import os\nDB = os.environ['APP_DB_URL']\nDEBUG = os.environ.get('APP_DEBUG', '0')\n")
    (r / "tests" / "test_app.py").write_text(
        "import os, subprocess, shutil, requests\n\ndef test_a():\n    assert os.getenv('API_TOKEN')\n    subprocess.run(['ffmpeg', '-version'])\n    shutil.which('git')\n"
        "    requests.get('https://api.thirdparty.io/v1/ping')\n    os.environ.get('OPTIONAL_X', 'dflt')\n")
    (r / "docker-compose.yml").write_text("services: {}\n")
    g("add", "."); g("commit", "-qm", "base")
    (r / "local_data").mkdir(); (r / "local_data" / "fixture.json").write_text("{}")   # ignored, exists only here
    (r / "cache.sqlite").write_text("x")
    (r / ".venv").mkdir(); (r / ".venv" / "junk").write_text("x")   # noise: must not be listed
    return r


class Manifest(unittest.TestCase):
    def test_names_only_and_categories_from_a_realistic_repository(self):
        with tempfile.TemporaryDirectory() as d:
            r = mkrepo(d)
            m = manifest.build(r, ["app.py"], {"python_version": "3.10.1", "platform": "Linux"}, "3.13.5", "Darwin")
            cats = {i["category"]: i for i in m["items"]}
            env = " ".join(cats["environment variables"]["names"])
            self.assertIn("APP_DB_URL (required", env); self.assertIn("APP_DEBUG", env); self.assertIn("API_TOKEN", env); self.assertIn("OPTIONAL_X", env)
            self.assertEqual(set(cats["external programs the tests invoke"]["names"]), {"ffmpeg", "git"})
            net = " ".join(cats["network use"]["names"]); self.assertIn("requests", net); self.assertIn("api.thirdparty.io", net)
            self.assertIn("docker-compose.yml", " ".join(cats["service and environment files present"]["names"]))
            ign = " ".join(cats["git-ignored files in the working tree"]["names"])
            self.assertIn("local_data", ign); self.assertIn("cache.sqlite", ign); self.assertNotIn(".venv", ign)
            self.assertEqual(len(cats["interpreter or operating system differs"]["names"]), 2)
            self.assertNotIn("secret", json.dumps(m).lower())   # values are never read

    def test_environment_values_are_never_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            r = mkrepo(d)
            os.environ["APP_DB_URL"] = "postgres://user:SECRETVALUE@host/db"
            try:
                self.assertNotIn("SECRETVALUE", json.dumps(manifest.build(r, ["app.py"])))
            finally:
                os.environ.pop("APP_DB_URL", None)

    def test_a_clean_repository_says_so_without_claiming_certainty(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d) / "r"; r.mkdir()
            g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
            g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
            (r / "lib.py").write_text("def f():\n    return 1\n"); g("add", "."); g("commit", "-qm", "x")
            m = manifest.build(r, ["lib.py"])
            self.assertEqual(m["items"], [])
            txt = "\n".join(manifest.render_text(m))
            self.assertIn("Nothing of these kinds was found", txt); self.assertIn("not proof", txt)

    def test_hostile_source_is_parsed_not_executed_and_control_characters_are_stripped(self):
        with tempfile.TemporaryDirectory() as d:
            r = mkrepo(d)
            (r / "tests" / "test_evil.py").write_text("import os\nos.system('touch PWNED')\nX = os.environ['EVIL\\x1b[31mNAME']\ndef broken(:\n")
            m = manifest.build(r, [])
            self.assertFalse((r / "PWNED").exists())
            self.assertNotIn("\x1b", json.dumps(m))

    def test_the_pack_renders_the_manifest_in_text_markdown_and_html(self):
        with tempfile.TemporaryDirectory() as d:
            r = mkrepo(d)
            p = {"version": 1, "receipt": {"commit": "a" * 40, "dirty": False, "base": "HEAD~1", "command": "python -m pytest -q", "replay_python": "3.13.5", "created": "x", "valid_for": "this exact commit"},
                 "contexts": [], "reproducibility": {"code": "none", "text": "n/a"}, "coverage": {"available": False, "reason": "x"}, "limits": pack.LIMITS, "manifest": manifest.build(r, ["app.py"])}
            import html
            txt = "\n".join(pack.render_text(p)); md = "\n".join(pack.render_markdown(p, lambda x, n=200: str(x)[:n])); h = pack.render_html(p, lambda x: html.escape(str(x)))
            for s in (txt, md, h):
                self.assertIn("Not reproduced by this replay", s); self.assertIn("APP_DB_URL", s)
            self.assertIn("recorded, not judged", txt)


if __name__ == "__main__":
    unittest.main()
