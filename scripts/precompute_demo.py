"""Save the local engine's output for the 9 demo documents in data/demo_cache/ (keyed by file hash).

The free Render server has ~0.1 CPU: reading all 9 live takes minutes. With this, "Try the demo bills" is instant;
every other upload is still read live. Rerun after changing the extractor:  python scripts/precompute_demo.py
"""
import hashlib
import json
import mimetypes
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["EXTRACTOR"] = "local"  # the engine the hosted demo runs
from backend.app import DEMO_CACHE, SAMPLE_RE, SAMPLES, read  # noqa: E402

DEMO_CACHE.mkdir(parents=True, exist_ok=True)
for old in DEMO_CACHE.glob("*.json"):
    old.unlink()
for path in sorted(p for p in SAMPLES.glob("*") if SAMPLE_RE.fullmatch(p.name)):
    data = path.read_bytes()
    doc, _ = read(data, mimetypes.guess_type(path.name)[0])
    doc["engine"] += " (precomputed demo)"
    (DEMO_CACHE / f"{hashlib.sha256(data).hexdigest()}.json").write_text(json.dumps(doc, indent=1))
    print(path.name, "->", len(doc["sources"]), "highlights")
