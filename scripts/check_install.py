"""Wait for the installed dashboard and verify it is the expected version."""
import json
import time
from urllib.request import urlopen

from ais_atis_bridge import __version__
from ais_atis_bridge.config import load


def check():
    settings = load()
    host = settings['web_host']
    if host in ('0.0.0.0', '::'): host = '127.0.0.1'
    if ':' in host: host = '[' + host + ']'
    base = f"http://{host}:{settings['web_port']}"
    error = 'not ready'
    for _ in range(30):
        try:
            with urlopen(base + '/api/status', timeout=1) as response:
                data = json.load(response)
            if data.get('version') != __version__:
                raise ValueError('Dashboard version does not match installed package')
            print(f"PASS dashboard {__version__}; receiver: {data['receiver']['state']}")
            print(f"Open http://<device-IP>:{settings['web_port']}")
            if data['receiver'].get('error'): print('Receiver warning: ' + data['receiver']['error'])
            return
        except (OSError, ValueError, KeyError) as exc:
            error = str(exc)
            time.sleep(1)
    raise SystemExit('Dashboard check failed: ' + error + '\nCheck: sudo journalctl -u ais-atis-bridge -n 40 --no-pager')


if __name__ == '__main__': check()
