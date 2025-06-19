#!/usr/bin/env python3
import re
import json
import base64
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

CHANNEL_AUTH_FILE = "channelAuth.txt"
OUTPUT_JSON_FILE = "channelKeys.json"

# shared headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0",
    "Origin":     "https://forcedtoplay.xyz"
}

def parse_channel_auth_blocks(file_path):
    with open(file_path, 'r') as f:
        lines = [l.strip() for l in f]
    i = 0
    while i < len(lines):
        m = re.match(r'var channelKey\s*=\s*"([^"]+)"', lines[i])
        if m and i+3 < len(lines):
            key = m.group(1)
            ts  = re.search(r'var authTs\s*=\s*"([^"]+)"', lines[i+1])
            rnd = re.search(r'var authRnd\s*=\s*"([^"]+)"', lines[i+2])
            sig = re.search(r'var authSig\s*=\s*"([^"]+)"', lines[i+3])
            if ts and rnd and sig:
                yield key, ts.group(1), rnd.group(1), sig.group(1)
                i += 4
                continue
        i += 1

def fetch_json(url):
    req = Request(url, headers=HEADERS, method="GET")
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode('utf-8'))

def fetch_text(url):
    req = Request(url, headers=HEADERS, method="GET")
    with urlopen(req, timeout=15) as resp:
        return resp.read().decode('utf-8')

def fetch_binary(url):
    req = Request(url, headers=HEADERS, method="GET")
    with urlopen(req, timeout=15) as resp:
        return resp.read()

def main():
    results = {}
    for key, ts, rnd, sig in parse_channel_auth_blocks(CHANNEL_AUTH_FILE):
        # 1) call auth.php
        auth_url = (
            "https://top2new.newkso.ru/auth.php"
            f"?channel_id={key}&ts={ts}&rnd={rnd}&sig={sig}"
        )
        try:
            resp = fetch_json(auth_url)
        except Exception as e:
            print(f"[{key}] auth.php error: {e}")
            continue

        if resp.get("status") != "ok":
            print(f"[{key}] auth.php returned not-ok: {resp}")
            continue

        # 2) fetch the m3u8
        m3u8_url = f"https://zekonew.newkso.ru/zeko/{key}/mono.m3u8"
        try:
            playlist = fetch_text(m3u8_url)
        except Exception as e:
            print(f"[{key}] playlist fetch error: {e}")
            continue

        # 3) extract EXT-X-KEY URI
        key_line = next(
            (l for l in playlist.splitlines() if l.startswith("#EXT-X-KEY")), 
            None
        )
        if not key_line:
            print(f"[{key}] EXT-X-KEY line not found")
            continue

        m = re.search(r'URI="([^"]+)"', key_line)
        if not m:
            print(f"[{key}] could not parse URI from: {key_line}")
            continue
        key_uri = m.group(1)

        # 4) fetch the key bytes
        try:
            raw = fetch_binary(key_uri)
        except Exception as e:
            print(f"[{key}] key fetch error: {e}")
            continue

        if len(raw) != 16:
            print(f"[{key}] unexpected key length: {len(raw)}")
            continue

        # 5) store Base64-encoded
        results[key] = base64.b64encode(raw).decode('ascii')

        # slight pause to avoid hammering
        time.sleep(0.2)

    # write out JSON
    with open(OUTPUT_JSON_FILE, 'w') as jf:
        json.dump(results, jf, indent=2)
    print(f"Wrote {len(results)} keys to {OUTPUT_JSON_FILE}")

if __name__ == "__main__":
    main()
