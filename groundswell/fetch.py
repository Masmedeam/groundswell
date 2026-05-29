"""Robust downloads via curl subprocess, with a Bright Data Web Unlocker fallback.

Why curl and not requests: on this network, Python requests' TLS fingerprint gets
tarpitted by Cloudflare-fronted hosts (e.g. FRED) — requests hangs at the timeout
while curl returns instantly. curl also gives binary-safe ranged downloads, which we
need because Zillow's S3 throttles full GETs (403) but serves range requests (206).
"""
import json
import os
import subprocess
import tempfile

from .config import BRIGHTDATA_TOKEN, BRIGHTDATA_ZONE

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _looks_ok(text, expect_prefix=None):
    if not text:
        return False
    head = text.lstrip()[:200]
    if head.startswith("<?xml") or "<Error>" in head or "<html" in head.lower():
        return False
    if expect_prefix and not text.lstrip().lower().startswith(expect_prefix.lower()):
        return False
    return True


def curl_get(url, max_time=30, rng=None):
    """Small text fetch. Returns (http_code:str, body:str)."""
    cmd = ["curl", "-sL", "--max-time", str(max_time), "-H", f"User-Agent: {UA}"]
    if rng:
        cmd += ["-r", rng]
    cmd += ["-w", "\n%{http_code}", url]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=max_time + 10)
    except Exception as e:  # noqa: BLE001
        return "000", f"(curl error: {e})"
    body, _, code = res.stdout.rpartition("\n")
    return code.strip(), body


def _curl_to_file(url, path, rng=None, max_time=180):
    cmd = ["curl", "-sL", "--max-time", str(max_time), "-H", f"User-Agent: {UA}", "-w", "%{http_code}"]
    if rng:
        cmd += ["-r", rng]
    cmd += ["-o", path, url]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=max_time + 15)
    return res.stdout.strip()


def download_bytes(url, timeout=180):
    """Binary-safe full download (used for .xls). Returns bytes or None."""
    fd, tmp = tempfile.mkstemp()
    os.close(fd)
    try:
        code = _curl_to_file(url, tmp, max_time=timeout)
        if code in ("200", "206"):
            with open(tmp, "rb") as f:
                return f.read()
        return None
    finally:
        os.unlink(tmp)


def download_direct(url, timeout=180):
    fd, tmp = tempfile.mkstemp()
    os.close(fd)
    try:
        code = _curl_to_file(url, tmp, max_time=timeout)
        if code == "200":
            with open(tmp, "rb") as f:
                data = f.read().decode("utf-8", "replace")
            if _looks_ok(data):
                return data
        raise RuntimeError(f"direct {code}")
    finally:
        os.unlink(tmp)


def download_ranged(url, chunk=8 * 1024 * 1024, timeout=120, max_chunks=800):
    """Binary-accurate ranged download (Zillow S3 serves 206 even when full GET 403s)."""
    buf, start = bytearray(), 0
    for _ in range(max_chunks):
        fd, tmp = tempfile.mkstemp()
        os.close(fd)
        try:
            code = _curl_to_file(url, tmp, rng=f"{start}-{start + chunk - 1}", max_time=timeout)
            if code not in ("206", "200"):
                raise RuntimeError(f"ranged {code} at byte {start}")
            with open(tmp, "rb") as f:
                b = f.read()
        finally:
            os.unlink(tmp)
        buf += b
        if code == "200" or len(b) < chunk:
            break
        start += len(b)
    return bytes(buf).decode("utf-8", "replace")


def download_brightdata(url, timeout=300):
    payload = json.dumps({"zone": BRIGHTDATA_ZONE, "url": url, "format": "raw"})
    cmd = [
        "curl", "-s", "--max-time", str(timeout), "https://api.brightdata.com/request",
        "-H", "Content-Type: application/json",
        "-H", f"Authorization: Bearer {BRIGHTDATA_TOKEN}",
        "-d", payload,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 15)
    return res.stdout


def fetch_text(url, expect_prefix=None):
    """Return (text, method). Tries curl direct, curl ranged, then Bright Data."""
    last = None
    for method in (download_direct, download_ranged, download_brightdata):
        try:
            text = method(url)
            if _looks_ok(text, expect_prefix):
                return text, method.__name__
            last = f"{method.__name__}: bad/blocked content"
        except Exception as e:  # noqa: BLE001
            last = f"{method.__name__}: {e}"
    raise RuntimeError(f"all download methods failed for {url} ({last})")


def url_exists(url, timeout=30):
    code, body = curl_get(url, max_time=timeout, rng="0-300")
    return code in ("200", "206") and _looks_ok(body + "x")
