#!/usr/bin/env python3
import re
import json
import base64
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

CHANNEL_AUTH_FILE = "channelAuth.txt"
OUTPUT_JSON_FILE = "channelKeys.json"

# HTTP headers to send on each auth.php request
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0",
    "Origin":     "https://forcedtoplay.xyz"
}

def parse_channel_auth_blocks(file_path):
    """
    Reads channelAuth.txt and yields tuples:
      (channel_key, auth_ts, auth_rnd, auth_sig)
    """
    with open(file_path, 'r') as f:
        lines = [l.strip() for l in f]
    i = 0
    while i < len(lines):
        m = re.match(r'var channelKey\s*=\s*"([^"]+)"', lines[i])
        if m and i+3 < len(lines):
            key = m.group(1)
            ts = re.search(r'var authTs\s*=\s*"([^"]+)"', lines[i+1])
            rnd= re.search(r'var authRnd\s*=\s*"([^"]+)"', lines[i+2])
            sig= re.search(r'var authSig\s*=\s*"([^"]+)"', lines[i+3])
            if ts and rnd and sig:
                yield key, ts.group(1), rnd.group(1), sig.group(1)
                i += 4
                continue
        i += 1

def fetch_binary_key(channel_key, ts, rnd, sig):
    """
    GETs the auth.php URL and returns the raw 16-byte body.
    """
    url = (
        "https://top2new.newkso.ru/auth.php"
        f"?channel_id={channel_key}"
        f"&ts={ts}&rnd={rnd}&sig={sig}"
    )
    req = Request(url, headers=HEADERS, method="GET")
    try:
        with urlopen(req, timeout=15) as resp:
            # Should be 16 bytes
            body = resp.read()
            if len(body) != 16:
                print(f"Warning: Expected 16 bytes for {channel_key}, got {len(body)}")
            return body
    except (HTTPError, URLError) as e:
        print(f"Error fetching key for {channel_key}: {e}")
        return None

def main():
    results = {}
    for key, ts, rnd, sig in parse_channel_auth_blocks(CHANNEL_AUTH_FILE):
        binary = fetch_binary_key(key, ts, rnd, sig)
        if binary:
            # JSON can’t hold raw bytes, so Base64-encode them
            b64 = base64.b64encode(binary).decode('ascii')
            results[key] = b64

    # Write out the mapping channelKey → Base64(key)
    with open(OUTPUT_JSON_FILE, 'w') as jf:
        json.dump(results, jf, indent=2)
    print(f"Wrote {len(results)} entries to {OUTPUT_JSON_FILE}")

if __name__ == "__main__":
    main()
