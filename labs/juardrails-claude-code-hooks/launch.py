#!/usr/bin/env python3
"""Start the private Juardrails service and install its Claude Code project pack."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import ipaddress
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parent
DATA = ROOT / '.data'
BIN = ROOT / 'bin' / 'juardrails'
REAL_BIN = ROOT / 'bin' / 'juardrails-real'
PROJECT = ROOT / 'target-project'
POLICY_ID = 'claude-code-tool-use'


def read_config():
    path = ROOT / '.env'
    if not path.exists():
        raise RuntimeError('Create .env from .env.example and set REQUESTY_API_KEY.')
    values = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key):
            raise RuntimeError(f'Invalid .env line {number}. Use KEY=value.')
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    if not values.get('REQUESTY_API_KEY'):
        raise RuntimeError('REQUESTY_API_KEY is missing from .env.')
    base = values.get('BASE_URL', 'https://router.requesty.ai/v1').rstrip('/')
    if base not in {'https://router.requesty.ai/v1', 'https://router.eu.requesty.ai/v1'}:
        raise RuntimeError('BASE_URL must be an official Requesty /v1 router URL.')
    values['BASE_URL'] = base
    if values.get('JEV_PROVIDER', 'requesty') != 'requesty':
        raise RuntimeError('This lab requires JEV_PROVIDER=requesty.')
    return values


def check_port(port):
    with socket.socket() as sock:
        try:
            sock.bind(('0.0.0.0', port))
        except OSError as error:
            raise RuntimeError(f'Port {port} is already in use.') from error


def browser_host():
    try:
        result = subprocess.run(['serverip'], capture_output=True, text=True,
                                timeout=20, check=True)
        address = ipaddress.ip_address(result.stdout.strip())
        return f'[{address}]' if address.version == 6 else str(address)
    except (OSError, ValueError, subprocess.SubprocessError):
        return '<LAB_IP>'


def cli(*args, check=True):
    result = subprocess.run([str(BIN), 'cli', *args], cwd=ROOT, capture_output=True,
                            text=True, check=False)
    if check and result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip() or 'Juardrails CLI failed.')
    return result


def prepare_identity(port):
    credential = DATA / 'cli-home' / '.juardrails' / 'credentials.json'
    database = DATA / 'juardrails.sqlite'
    if credential.exists() and not database.exists():
        raise RuntimeError('CLI credential exists without its database. Inspect .data before resetting the lab.')
    if database.exists() and not credential.exists():
        raise RuntimeError('Database exists without its CLI credential. Inspect .data before resetting the lab.')
    if credential.exists():
        return
    command = [str(BIN), 'bootstrap', '-db', str(database),
               '-audit-log', str(DATA / 'audit.jsonl'),
               '-url', f'http://127.0.0.1:{port}']
    subprocess.run(command, cwd=ROOT, check=True)


def wait_until_ready(process, port):
    url = f'http://127.0.0.1:{port}/healthz'
    for _ in range(150):
        if process.poll() is not None:
            raise RuntimeError('Juardrails exited. Inspect .data/juardrails.log.')
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(0.1)
    raise RuntimeError('Juardrails did not become ready. Inspect .data/juardrails.log.')


def provision_scoped_credential(port):
    """Replace bootstrap CLI admin access with policy-only lab access."""
    path = DATA / 'cli-home' / '.juardrails' / 'credentials.json'
    bootstrap = json.loads(path.read_text())
    if bootstrap.get('lab_scope') == 'claude-code-policy':
        return
    headers = {'Authorization': 'Bearer ' + bootstrap['token'],
               'X-Juardrails-Namespace': 'root', 'Content-Type': 'application/json'}
    base = f'http://127.0.0.1:{port}/api/v1'

    def api(method, endpoint, body=None):
        payload = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(base + endpoint, data=payload,
                                         headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'Service credential setup failed at {endpoint}: HTTP {error.code}') from error

    grant = 'claude-code-lab-policy-access'
    policies = api('GET', '/admin/access-policies')['items']
    if not any(item['name'] == grant for item in policies):
        api('POST', '/admin/access-policies', {'name': grant, 'rules': [{
            'namespace': 'root', 'actions': [
                'policies:read', 'policies:create', 'policies:update',
                'policies:evaluate', 'policies:simulate', 'evaluations:read'
            ]}]})
    principals = api('GET', '/admin/principals')['items']
    principal = next((item for item in principals if item['name'] == 'claude-code-lab'), None)
    if principal is None:
        principal = api('POST', '/admin/principals',
                        {'name': 'claude-code-lab', 'kind': 'service'})
    if principal['kind'] != 'service' or principal.get('disabled'):
        raise RuntimeError('The claude-code-lab service account is unavailable.')
    api('PUT', f"/admin/principals/{principal['id']}/bindings", {'policies': [grant]})
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat().replace('+00:00', 'Z')
    issued = api('POST', '/admin/tokens',
                 {'principal_id': principal['id'], 'name': 'claude-code-lab', 'expires_at': expires})
    limited = {'url': bootstrap['url'], 'token': issued['token'],
               'lab_scope': 'claude-code-policy'}
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(limited, indent=2))
    temporary.chmod(0o600)
    temporary.replace(path)


def prepare_pack():
    installer = ROOT / 'vendor' / 'claude-code-pack' / 'install.py'
    for directory in (ROOT, PROJECT):
        settings = directory / '.claude' / 'settings.json'
        hook = directory / '.claude' / 'hooks' / 'juardrails_pre_tool_use.py'
        if not settings.exists() or not hook.exists():
            subprocess.run([sys.executable, str(installer), str(directory),
                            '--juard', str(BIN), '--no-apply'], cwd=ROOT, check=True)
    if cli('get', POLICY_ID, check=False).returncode:
        cli('apply', str(ROOT / 'policies' / 'claude-code-tool-use.yaml'))


def main():
    config = read_config()
    if not REAL_BIN.is_file():
        raise RuntimeError('Juardrails is missing from this lab VM. Contact the lab administrator.')
    DATA.mkdir(mode=0o700, exist_ok=True)
    DATA.chmod(0o700)
    (DATA / 'cli-home').mkdir(mode=0o700, exist_ok=True)
    port = 8080
    check_port(port)
    prepare_identity(port)
    server_env = os.environ.copy()
    server_env.update(config)
    server_env['JEV_PROVIDER'] = 'requesty'
    server_env['JEV_DEFAULT_MODEL'] = config.get('JEV_DEFAULT_MODEL', 'typesafe/jev-1.13.0')
    server_env['JEV_ENDPOINT_URL'] = config['BASE_URL'] + '/chat/completions'
    server_env.pop('JEV_API_KEY', None)
    server_env.pop('TYPESAFE_API_KEY', None)
    server = None
    pid_file = DATA / 'launcher.pid'
    stop_request = DATA / 'stop.request'
    stop_request.unlink(missing_ok=True)
    try:
        with (DATA / 'juardrails.log').open('a') as log:
            server = subprocess.Popen([str(REAL_BIN), '-addr', f'0.0.0.0:{port}',
                                       '-db', str(DATA / 'juardrails.sqlite'),
                                       '-audit-log', str(DATA / 'audit.jsonl')],
                                      cwd=ROOT, env=server_env, stdout=log, stderr=log)
            wait_until_ready(server, port)
            provision_scoped_credential(port)
            prepare_pack()
            pid_file.write_text(str(os.getpid()))
            print(f'Juardrails UI listening on 0.0.0.0:{port}')
            print(f'Local URL: http://127.0.0.1:{port}')
            print(f'Juardrails UI: http://{browser_host()}:{port}')
            print('Policy and Claude Code hooks are installed at the lab root and in target-project/.claude/.')
            print('In another terminal, run: python3 show-login.py')
            print('Keep this terminal running. Ctrl+C stops the service; history is preserved.', flush=True)
            while server.poll() is None:
                if stop_request.exists():
                    print('Stop requested. Juardrails is shutting down.')
                    return
                time.sleep(0.5)
            raise RuntimeError('Juardrails stopped unexpectedly. Inspect .data/juardrails.log.')
    finally:
        pid_file.unlink(missing_ok=True)
        stop_request.unlink(missing_ok=True)
        if server and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nJuardrails stopped. Policy history is preserved.')
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
