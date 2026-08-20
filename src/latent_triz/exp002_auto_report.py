"""Claim-free external-score publication verifier for EXP-002-AUTO."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any


class Exp002AutoPublicationError(ValueError):
    """Raised when an AUTO package is incomplete, mutable, or over-claimed."""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TERMINAL = frozenset({"auto_proxy_signal", "null", "failed", "non_interpretable", "incompatible"})


def _claim_free(item: Mapping[str, Any]) -> None:
    if item.get("scientific_status") != "exploratory" or item.get("evidence_eligible") is not False or item.get("expert_validated") is not False or item.get("claim_ids") != []:
        raise Exp002AutoPublicationError("AUTO publication attempted to promote an exploratory result")


def verify_auto_publication(
    *, manifest: Mapping[str, Any], results: Sequence[Mapping[str, Any]],
    read_external_asset: Callable[[str], bytes],
) -> None:
    """Verify result envelopes and external asset hashes without copying bytes."""
    if not isinstance(manifest, Mapping) or manifest.get("artifact_class") != "exp002-auto-publication-manifest" or manifest.get("protocol_id") != "exp002-auto-v1.0.0":
        raise Exp002AutoPublicationError("unexpected AUTO publication manifest")
    if manifest.get("status") not in {"not_ready", "ready", "published"}:
        raise Exp002AutoPublicationError("AUTO publication manifest status is invalid")
    _claim_free(manifest)
    if isinstance(results, (str, bytes, bytearray)) or not isinstance(results, Sequence):
        raise Exp002AutoPublicationError("AUTO results must be a sequence")
    for result in results:
        if not isinstance(result, Mapping) or result.get("artifact_class") != "exp002-auto-result" or result.get("protocol_id") != "exp002-auto-v1.0.0":
            raise Exp002AutoPublicationError("unexpected AUTO result envelope")
        if result.get("status") not in _TERMINAL:
            raise Exp002AutoPublicationError("AUTO result is not terminal")
        _claim_free(result)
    assets = manifest.get("external_score_assets")
    if isinstance(assets, (str, bytes, bytearray)) or not isinstance(assets, Sequence):
        raise Exp002AutoPublicationError("AUTO external score assets are malformed")
    for asset in assets:
        if not isinstance(asset, Mapping) or not isinstance(asset.get("locator"), str) or not asset["locator"].startswith("artifacts/exp002-auto/") or not isinstance(asset.get("sha256"), str) or not _SHA256.fullmatch(asset["sha256"]):
            raise Exp002AutoPublicationError("AUTO score asset locator or hash is invalid")
        payload = read_external_asset(asset["locator"])
        if not isinstance(payload, bytes) or hashlib.sha256(payload).hexdigest() != asset["sha256"]:
            raise Exp002AutoPublicationError("AUTO external score asset is missing or hash-mutated")


__all__ = ["Exp002AutoPublicationError", "verify_auto_publication"]
