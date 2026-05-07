"""Cross-domain call with raw dict — no typed schema validation at boundary, must fail."""

from argus.calibration.service import calibrate

# Raw dict passed across domain boundary without parsing
calibrate({"intent_tree": {}, "compute_graph": {}})
