#!/usr/bin/env python
"""Export the OpenAPI spec to openapi.json (handy for clients / docs)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blogsmith.api.main import create_app  # noqa: E402


def main() -> int:
    spec = create_app().openapi()
    out = Path(__file__).resolve().parents[1] / "openapi.json"
    out.write_text(json.dumps(spec, indent=2))
    print(f"Wrote {out} ({len(spec.get('paths', {}))} paths).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
