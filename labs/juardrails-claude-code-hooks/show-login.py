#!/usr/bin/env python3
"""Print the local Juardrails UI login without exposing the Requesty key."""
import json
from pathlib import Path

path = Path(__file__).resolve().parent / '.data' / 'bootstrap-admin.json'
if not path.exists():
    raise SystemExit('Start the lab first with bash start.sh.')
data = json.loads(path.read_text())
print('Juardrails UI username:', data.get('username', 'admin'))
print('Juardrails UI initial password:', data['password'])
