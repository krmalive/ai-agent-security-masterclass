#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 - <<'PY'
from pathlib import Path
import time
path = Path('.data/launcher.pid')
if not path.exists():
    raise SystemExit('No running lab is recorded. Use Ctrl+C in its terminal if needed.')
(path.parent / 'stop.request').write_text('stop\n')
for _ in range(100):
    if not path.exists():
        print('Lab stopped. Policy history is preserved.')
        break
    time.sleep(0.1)
else:
    raise SystemExit('Stop requested. If the service does not stop, use Ctrl+C in its terminal.')
PY
