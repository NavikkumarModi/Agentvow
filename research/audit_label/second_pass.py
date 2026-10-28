"""Reproduce the seeded 20% sample for the second labelling pass (pre-registration A1, point 2): the 30 labelled items with the smallest SHA-256(`seed|second|item id`), where the item id is the 10-hex suffix of the item file name.
Usage: python3 research/audit_label/second_pass.py   -> prints the list and checks it against docs/research/audit_data/second_pass_items.json"""
import glob
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = 6883625825084806765


def pick(ids, n=30):
    return sorted(ids, key=lambda i: hashlib.sha256(f"{SEED}|second|{i.split('_')[1]}".encode()).hexdigest())[:n]


if __name__ == "__main__":
    ids = [os.path.basename(f)[:-5] for f in sorted(glob.glob(str(ROOT / "docs/research/audit_data/items/*.json")))][:150]
    got = pick(ids)
    want = json.load(open(ROOT / "docs/research/audit_data/second_pass_items.json"))
    print(got)
    print("matches the recorded list:", got == want)
