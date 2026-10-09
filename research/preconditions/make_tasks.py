"""Generate the 12 pilot tasks (docs/research/forecast_grounding/PRECONDITIONS_PREREG.md). Deterministic. Output: data/preconditions/tasks/<id>/{repo,solution,meta.json}."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "preconditions" / "tasks"

PYPROJECT = '[build-system]\nrequires = ["setuptools>=61"]\nbuild-backend = "setuptools.build_meta"\n\n[project]\nname = "pilot"\nversion = "0.1.0"\n{deps}\n[tool.setuptools]\npackages = ["pilot"]\n'
README = "# pilot\n\nSmall library. Tests live in `tests/`; run them with `pytest`.\n{extra}"


def task(id_, trap, desc, files, solution=None, ref_recipe=None, deps=None, prep=None, inexpressible=False, readme_extra="", gitignore=""):
    return dict(id=id_, trap=trap, desc=desc, files=files, solution=solution or {}, ref_recipe=ref_recipe, deps=deps, prep=prep or [],
                inexpressible=inexpressible, readme_extra=readme_extra, gitignore=gitignore)


T = []
# --- trap 1: undeclared package from S (agent env has it, the repository does not declare it)
T.append(task("t1a_requests_undeclared", "undeclared_dependency", "build_session() with requests",
    {"pilot/__init__.py": "", "pilot/client.py": "def build_session():\n    raise NotImplementedError\n",
     "tests/test_client.py": "import requests\nfrom pilot.client import build_session\n\n\ndef test_session():\n    s = build_session()\n    assert isinstance(s, requests.Session)\n    assert s.headers['User-Agent'] == 'pilot/1.0'\n"},
    {"pilot/client.py": "import requests\n\n\ndef build_session():\n    s = requests.Session()\n    s.headers['User-Agent'] = 'pilot/1.0'\n    return s\n"},
    {"setup": ["pip install pytest requests"], "test": "pytest -q"}))
T.append(task("t1b_numpy_undeclared", "undeclared_dependency", "moving_average with numpy",
    {"pilot/__init__.py": "", "pilot/stats.py": "def moving_average(xs, n):\n    raise NotImplementedError\n",
     "tests/test_stats.py": "import numpy as np\nfrom pilot.stats import moving_average\n\n\ndef test_ma():\n    out = moving_average([1, 2, 3, 4], 2)\n    assert isinstance(out, np.ndarray)\n    assert np.allclose(out, [1.5, 2.5, 3.5])\n"},
    {"pilot/stats.py": "import numpy as np\n\n\ndef moving_average(xs, n):\n    return np.convolve(np.asarray(xs, dtype=float), np.ones(n) / n, mode='valid')\n"},
    {"setup": ["pip install pytest numpy"], "test": "pytest -q"}))
# --- trap 2: declared in the repository (control)
T.append(task("t2a_requests_declared", "declared_dependency", "build_session() with requests (declared)",
    {"pilot/__init__.py": "", "pilot/client.py": "def build_session():\n    raise NotImplementedError\n",
     "tests/test_client.py": "import requests\nfrom pilot.client import build_session\n\n\ndef test_session():\n    s = build_session()\n    assert isinstance(s, requests.Session)\n    assert s.headers['User-Agent'] == 'pilot/1.0'\n"},
    {"pilot/client.py": "import requests\n\n\ndef build_session():\n    s = requests.Session()\n    s.headers['User-Agent'] = 'pilot/1.0'\n    return s\n"},
    {"setup": ["pip install pytest", "pip install ."], "test": "pytest -q"}, deps=["requests"]))
T.append(task("t2b_attrs_declared", "declared_dependency", "Point model with attrs (declared)",
    {"pilot/__init__.py": "", "pilot/models.py": "class Point:\n    pass\n",
     "tests/test_models.py": "import attrs\nfrom pilot.models import Point\n\n\ndef test_point():\n    p = Point(1, 2)\n    assert attrs.has(Point)\n    assert p == Point(1, 2)\n    assert p.x == 1 and p.y == 2\n"},
    {"pilot/models.py": "import attrs\n\n\n@attrs.define\nclass Point:\n    x: int\n    y: int\n"},
    {"setup": ["pip install pytest", "pip install ."], "test": "pytest -q"}, deps=["attrs"]))
# --- trap 3: environment variable the tests need
T.append(task("t3a_env_mode", "env_var", "tests need PKG_MODE=test",
    {"pilot/__init__.py": "", "pilot/config.py": "import os\n\n\ndef load():\n    return {'mode': os.environ['PKG_MODE']}\n",
     "tests/test_config.py": "from pilot.config import load\n\n\ndef test_mode():\n    assert load()['mode'] == 'test'\n",
     ".env.example": "PKG_MODE=test\n"},
    {}, {"setup": ["pip install pytest"], "test": "pytest -q", "env": {"PKG_MODE": "test"}},
    readme_extra="\nConfiguration comes from environment variables; see `.env.example` (tests expect `PKG_MODE=test`).\n"))
T.append(task("t3b_env_db", "env_var", "tests need PILOT_DB=:memory:",
    {"pilot/__init__.py": "", "pilot/db.py": "import os\nimport sqlite3\n\n\ndef connect():\n    return sqlite3.connect(os.environ['PILOT_DB'])\n",
     "tests/test_db.py": "from pilot.db import connect\n\n\ndef test_roundtrip():\n    c = connect()\n    c.execute('create table t (x integer)')\n    c.execute('insert into t values (7)')\n    assert c.execute('select x from t').fetchone() == (7,)\n",
     ".env.example": "PILOT_DB=:memory:\n"},
    {}, {"setup": ["pip install pytest"], "test": "pytest -q", "env": {"PILOT_DB": ":memory:"}},
    readme_extra="\nConfiguration comes from environment variables; see `.env.example`.\n"))
# --- trap 4: newest release breaks existing code; an older pin works, or the code can be fixed
T.append(task("t4a_numpy_removed_api", "version_pin", "np.float_ removed in numpy 2",
    {"pilot/__init__.py": "", "pilot/vec.py": "import numpy as np\n\n\ndef to_float(x):\n    return np.float_(x)\n",
     "tests/test_vec.py": "import numpy as np\nfrom pilot.vec import to_float\n\n\ndef test_to_float():\n    assert to_float('1.5') == 1.5\n    assert isinstance(to_float(1), np.floating)\n"},
    {"pilot/vec.py": "import numpy as np\n\n\ndef to_float(x):\n    return np.float64(x)\n"},
    {"setup": ["pip install pytest numpy"], "test": "pytest -q"}))
T.append(task("t4b_yaml_load", "version_pin", "yaml.load without Loader fails in PyYAML 6",
    {"pilot/__init__.py": "", "pilot/cfg.py": "import yaml\n\n\ndef parse(s):\n    return yaml.load(s)\n",
     "tests/test_cfg.py": "from pilot.cfg import parse\n\n\ndef test_parse():\n    assert parse('a: 1\\nb: [1, 2]') == {'a': 1, 'b': [1, 2]}\n"},
    {"pilot/cfg.py": "import yaml\n\n\ndef parse(s):\n    return yaml.safe_load(s)\n"},
    {"setup": ["pip install pytest pyyaml"], "test": "pytest -q"}))
# --- trap 5: a generated, git-ignored fixture (not expressible as a pip step)
T.append(task("t5a_generated_json", "generated_file", "tests read tests/data/cities.json generated by a script",
    {"pilot/__init__.py": "", "pilot/loader.py": "def load_cities(path):\n    raise NotImplementedError\n",
     "scripts/make_fixture.py": "import json, pathlib\np = pathlib.Path('tests/data'); p.mkdir(parents=True, exist_ok=True)\n(p / 'cities.json').write_text(json.dumps(['a', 'b', 'c']))\n",
     "tests/test_loader.py": "from pilot.loader import load_cities\n\n\ndef test_cities():\n    assert len(load_cities('tests/data/cities.json')) == 3\n"},
    {"pilot/loader.py": "import json\n\n\ndef load_cities(path):\n    return json.load(open(path))\n"},
    {"setup": ["pip install pytest"], "test": "pytest -q"}, prep=["python scripts/make_fixture.py"], inexpressible=True,
    readme_extra="\nThe fixture `tests/data/cities.json` is generated by `scripts/make_fixture.py` and is not committed.\n", gitignore="tests/data/\n"))
T.append(task("t5b_generated_db", "generated_file", "tests read tests/data/app.db generated by a script",
    {"pilot/__init__.py": "", "pilot/store.py": "def count(path):\n    raise NotImplementedError\n",
     "scripts/make_fixture.py": "import pathlib, sqlite3\np = pathlib.Path('tests/data'); p.mkdir(parents=True, exist_ok=True)\nc = sqlite3.connect(p / 'app.db'); c.execute('create table t (x)'); c.executemany('insert into t values (?)', [(1,), (2,)]); c.commit()\n",
     "tests/test_store.py": "from pilot.store import count\n\n\ndef test_count():\n    assert count('tests/data/app.db') == 2\n"},
    {"pilot/store.py": "import sqlite3\n\n\ndef count(path):\n    return sqlite3.connect(path).execute('select count(*) from t').fetchone()[0]\n"},
    {"setup": ["pip install pytest"], "test": "pytest -q"}, prep=["python scripts/make_fixture.py"], inexpressible=True,
    readme_extra="\nThe fixture `tests/data/app.db` is generated by `scripts/make_fixture.py` and is not committed.\n", gitignore="tests/data/\n"))
# --- trap 6: no precondition (control)
T.append(task("t6a_slugify", "none", "slugify (pure python)",
    {"pilot/__init__.py": "", "pilot/textutil.py": "def slugify(s):\n    raise NotImplementedError\n",
     "tests/test_text.py": "from pilot.textutil import slugify\n\n\ndef test_slug():\n    assert slugify('Hello, World!') == 'hello-world'\n    assert slugify('  A  B ') == 'a-b'\n"},
    {"pilot/textutil.py": "import re\n\n\ndef slugify(s):\n    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')\n"},
    {"setup": ["pip install pytest"], "test": "pytest -q"}))
T.append(task("t6b_chunks", "none", "chunks (pure python)",
    {"pilot/__init__.py": "", "pilot/seq.py": "def chunks(xs, n):\n    raise NotImplementedError\n",
     "tests/test_seq.py": "from pilot.seq import chunks\n\n\ndef test_chunks():\n    assert chunks([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]\n    assert chunks([], 3) == []\n"},
    {"pilot/seq.py": "def chunks(xs, n):\n    return [list(xs[i:i + n]) for i in range(0, len(xs), n)]\n"},
    {"setup": ["pip install pytest"], "test": "pytest -q"}))


def write(root: Path, files: dict):
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    for t in T:
        d = OUT / t["id"]
        repo = d / "repo"
        deps = f"dependencies = {json.dumps(t['deps'])}\n" if t["deps"] else ""
        write(repo, {"pyproject.toml": PYPROJECT.format(deps=deps), "README.md": README.format(extra=t["readme_extra"]), **t["files"]})
        if t["gitignore"]:
            write(repo, {".gitignore": t["gitignore"]})
        write(d / "solution", t["solution"])
        meta = {k: t[k] for k in ("id", "trap", "desc", "ref_recipe", "prep", "inexpressible")}
        (d / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"{len(T)} tasks in {OUT}")


if __name__ == "__main__":
    main()
