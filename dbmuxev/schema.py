"""
JSON schema validation of objects (needs ``jsonschema``: pip install jsonschema).

The whole repository check (schema + bit overlaps, references, file names...)
is ``tools/validate.py``; this module validates single objects before saving them.
"""
import json
import os

__all__ = ['schema_errors', 'load_schema', 'SCHEMA_KINDS']

# object class -> definition name in schemas/dbmuxev.schema.json
SCHEMA_KINDS = {
    'Message': 'message', 'Signal': 'signal', 'Architectures': 'architectures', 'Variant': 'arch_variant',
    'NodeSet': 'nodes', 'Node': 'node', 'Car': 'car', 'CarVersion': 'car_version', 'DiagEcu': 'diag_ecu',
    'DiagData': 'diag_data', 'DtcTable': 'diag_dtcs', 'Routine': 'diag_routine', 'Ioctl': 'diag_ioctl',
    'DiagProtocol': 'diag_protocol',
}

_bundles = {}


def load_schema(path=None):
    """The schema bundle (schemas/dbmuxev.schema.json of the repository containing this package by default)"""
    if path is None:
        from .database import find_root
        path = os.path.join(find_root(), 'schemas', 'dbmuxev.schema.json')
    if path not in _bundles:
        with open(path, encoding='utf-8') as f:
            _bundles[path] = json.load(f)
    return _bundles[path]


def _json(obj):
    if isinstance(obj, dict):
        return {str(k): _json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json(v) for v in obj]
    if isinstance(obj, bool) or obj is None or isinstance(obj, (str, float)):
        return obj
    if isinstance(obj, int):
        return int(obj)
    return str(obj)


def schema_errors(obj, kind=None, schema_path=None):
    """List of 'path: message' schema errors of an object (or a dict with ``kind`` given)"""
    try:
        import jsonschema
    except ImportError as e:  # pragma: no cover
        raise ImportError('schema validation needs jsonschema: pip install jsonschema') from e
    if kind is None:
        kind = SCHEMA_KINDS.get(type(obj).__name__)
        if kind is None:
            raise ValueError(f'no schema for {type(obj).__name__}, give kind')
    data = obj.to_dict() if hasattr(obj, 'to_dict') else obj
    bundle = load_schema(schema_path)
    validator = jsonschema.Draft7Validator({'$ref': f'#/definitions/{kind}', 'definitions': bundle['definitions']})
    out = []
    for err in sorted(validator.iter_errors(_json(data)), key=lambda e: list(e.absolute_path)):
        where = '/'.join(str(p) for p in err.absolute_path) or '(root)'
        out.append(f'{where}: {err.message}')
    return out
