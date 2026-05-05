from __future__ import annotations

import json
from pathlib import Path


def load_result_payload(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
