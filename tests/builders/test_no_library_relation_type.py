"""Regression test: BTM feature parameters must never carry libraryRelationType.

Onshape's current /features endpoint rejects any parameter dict that includes
a `libraryRelationType` key with HTTP 400 BTWeirdStringValueException in
feature.parameters[0]. Several builders stamped `"libraryRelationType": "NONE"`
onto every parameter (copied from an outdated API example); this walks every
builder's actual `build()` output and fails if that key reappears anywhere.
"""

from typing import Any, Dict, List

from onshape_mcp.builders.boolean import BooleanBuilder
from onshape_mcp.builders.chamfer import ChamferBuilder
from onshape_mcp.builders.extrude import ExtrudeBuilder
from onshape_mcp.builders.fillet import FilletBuilder
from onshape_mcp.builders.mate import MateBuilder, MateConnectorBuilder
from onshape_mcp.builders.offset_plane import OffsetPlaneBuilder
from onshape_mcp.builders.pattern import CircularPatternBuilder, LinearPatternBuilder
from onshape_mcp.builders.revolve import RevolveBuilder
from onshape_mcp.builders.shell import ShellBuilder
from onshape_mcp.builders.sketch import SketchBuilder
from onshape_mcp.builders.sketch_constraints import serialize as serialize_constraint
from onshape_mcp.builders.thicken import ThickenBuilder


def _find_key(payload: Any, key: str, path: str = "$") -> List[str]:
    """Return every JSON path at which `key` appears anywhere in `payload`."""
    hits: List[str] = []
    if isinstance(payload, dict):
        for k, v in payload.items():
            if k == key:
                hits.append(f"{path}.{k}")
            hits.extend(_find_key(v, key, f"{path}.{k}"))
    elif isinstance(payload, list):
        for i, item in enumerate(payload):
            hits.extend(_find_key(item, key, f"{path}[{i}]"))
    return hits


def _built_payloads() -> Dict[str, Any]:
    """One real `build()` output per builder, using minimal valid setup."""
    return {
        "extrude": ExtrudeBuilder(sketch_feature_id="sketch1").build(),
        "fillet": FilletBuilder().add_edge("edge1").build(),
        "chamfer": ChamferBuilder().add_edge("edge1").build(),
        "boolean": BooleanBuilder().add_tool_body("body1").build(),
        "offset_plane": OffsetPlaneBuilder(reference_id="plane1").build(),
        "revolve": RevolveBuilder(sketch_feature_id="sketch1").build(),
        "shell": ShellBuilder().add_face("face1").build(),
        "linear_pattern": LinearPatternBuilder(direction_edge_id="edge1")
        .add_feature("feat1")
        .build(),
        "circular_pattern": CircularPatternBuilder().add_feature("feat1").build(),
        "sketch_constraint_entity_ref": serialize_constraint("HORIZONTAL", entity="line1"),
        "sketch_constraint_dimensioned": serialize_constraint(
            "DIAMETER", entity="circle1", value="5 mm"
        ),
        # Never had the bug — included so the walker's own correctness is
        # cross-checked against a known-clean payload, not just absence of test.
        "mate_connector": MateConnectorBuilder(face_id="face1").build(),
        "mate": MateBuilder().build(),
        "thicken": ThickenBuilder(name="Thicken", sketch_feature_id="sketch1")
        .set_thickness(1.0)
        .build(),
        "sketch": SketchBuilder(plane_id="plane1").add_rectangle((0, 0), (10, 5)).build(),
    }


def test_no_builder_emits_library_relation_type() -> None:
    """No builder payload may contain a `libraryRelationType` key anywhere.

    The live Onshape API rejects it with BTWeirdStringValueException.
    """
    offenders: Dict[str, List[str]] = {}
    for builder_name, payload in _built_payloads().items():
        hits = _find_key(payload, "libraryRelationType")
        if hits:
            offenders[builder_name] = hits

    assert not offenders, f"libraryRelationType found in builder output: {offenders}"
