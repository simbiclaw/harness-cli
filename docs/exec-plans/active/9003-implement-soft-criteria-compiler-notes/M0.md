# M0 — Compiler input schemas (9003)

### [plan-confirmed] — M0 scope well-defined

All three compiler input schemas + CalibrationManifest + two output schemas (AuthoredNode, ResidueManifest) match the spec. The spec (§3) and patches provide complete field definitions. No ambiguity about types or required vs. optional fields.

### [discovery] — No existing Pydantic models in src/argus/

`src/argus/types/` was empty scaffolding. `IntentsNode` existed only as a JSON schema in the pipeline spec HTML — never translated to Pydantic. All schemas built from scratch. This is consistent with 9002 M2 not yet having landed the runtime schemas.

### [discovery] — Pydantic model subscript access

Pydantic v2 BaseModel does not support `model["field"]` subscript access by default — only `model.field` attribute access works. The Row models needed the test adjusted to use `.kind` instead of `["kind"]`. This is standard Pydantic idiom.

### [plan-confirmed] — Layering clean

`src/argus/types/compiler_schemas.py` imports only stdlib + pydantic. No imports from other `argus.*` modules. This satisfies the `types/` layer fence in `docs/conventions/layering.md`.
