#!/usr/bin/env python3
"""Audit the no-model H1 expert collection packet."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latent_triz.h1_packet_audit import audit_h1_packet  # noqa: E402


if __name__ == "__main__":
    print(json.dumps(audit_h1_packet(repo_root=ROOT), indent=2, sort_keys=True))
