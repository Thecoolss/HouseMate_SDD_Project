"""Bounded post-deploy check: own database ready AND the expected commit is running."""
import json
import sys
import time
import urllib.error
import urllib.request


def wait_for_health(url, sha, budget=300):
    deadline = time.monotonic() + budget
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url.rstrip('/') + '/health', timeout=min(15, max(1, deadline - time.monotonic()))) as response:
                data = json.load(response)
                if response.status == 200 and data.get('status') == 'ok' and data.get('db') == 'ok' and data.get('version') == sha:
                    print(f'{url}: healthy at {sha}')
                    return
        except (OSError, ValueError, urllib.error.URLError):
            pass
        time.sleep(min(5, max(0, deadline - time.monotonic())))
    raise SystemExit(f'{url}: expected healthy commit {sha} not ready within {budget}s')


if __name__ == '__main__':
    wait_for_health(sys.argv[1], sys.argv[2])
