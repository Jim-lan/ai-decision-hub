"""Run with jsonschema 4.x and format dependencies installed."""
import json
from pathlib import Path
from uuid import UUID
from jsonschema import Draft202012Validator

schema = json.loads((Path(__file__).resolve().parents[1] / 'api/domain.schema.json').read_text())
Draft202012Validator.check_schema(schema)
validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
audit = schema['$defs']['AuditRecord']
record = {key: str(UUID(int=1)) for key in ['trace_id','owner_id','project_id','resource_id','event_id']}
record.update(schema_version=1, created_at='2026-11-09T00:00:00Z', action=audit['properties']['action']['enum'][0], outcome='accepted')
validator.validate(record)
for invalid in [dict(record, outcome='unsupported'), dict(record, raw_secret='forbidden'), {k:v for k,v in record.items() if k!='outcome'}]:
    if validator.is_valid(invalid):
        raise ValueError('Invalid audit fixture passed')
print('Domain schema and four audit fixtures passed')
