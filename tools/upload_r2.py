#!/usr/bin/env python3
"""Upload the clean masters to Cloudflare R2, ready for delivery.

What goes up is images/_originals/ — the unwatermarked copies. The
published images/ files carry a burned watermark and would be worthless
to a buyer; the whole point is that paying gets you the clean one.

The bucket stays private. Nothing here makes an object public: buyers
reach a file through a short-lived signed URL minted by the Edge
Function only after it has checked they actually bought that photograph.

Credentials come from .env.local, which is gitignored and never leaves
this machine. They are not in js/ and must not be — an R2 secret can
delete the whole bucket, unlike the Supabase anon key which is
constrained by policy and legitimately lives in the page.

    python3 tools/upload_r2.py --check     # credentials + bucket reachable
    python3 tools/upload_r2.py             # dry run: what would upload
    python3 tools/upload_r2.py --run
"""

import json
import os
import sys
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGINALS = os.path.join(ROOT, "images", "_originals")
ENV = os.path.join(ROOT, ".env.local")


def load_env():
    if not os.path.exists(ENV):
        sys.exit("No .env.local — copy .env.local.example to .env.local first.")
    env = {}
    for line in open(ENV):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    missing = [k for k in ("R2_ACCOUNT_ID", "R2_BUCKET", "R2_ACCESS_KEY_ID",
                           "R2_SECRET_ACCESS_KEY") if not env.get(k)]
    if missing:
        sys.exit("Missing in .env.local: " + ", ".join(missing))
    return env


def client(env):
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url="https://%s.r2.cloudflarestorage.com" % env["R2_ACCOUNT_ID"],
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4", region_name="auto"),
    )


def wanted():
    """Only photographs that are actually for sale — the portfolio work
    has no buyer, so there is no reason to put it in the bucket."""
    photos = json.load(open(os.path.join(ROOT, "data", "photos.json")))
    out = []
    for p in photos:
        if not p.get("game"):
            continue
        name = os.path.basename(p["src"])
        path = os.path.join(ORIGINALS, name)
        if os.path.exists(path):
            out.append((name, path, p["game"]))
    return out


def main():
    env = load_env()
    s3 = client(env)
    bucket = env["R2_BUCKET"]

    if "--check" in sys.argv:
        s3.head_bucket(Bucket=bucket)
        print("credentials OK, bucket '%s' reachable" % bucket)
        return

    have = set()
    token = None
    while True:
        kw = {"Bucket": bucket, "MaxKeys": 1000}
        if token:
            kw["ContinuationToken"] = token
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", []):
            have.add(o["Key"])
        if not r.get("IsTruncated"):
            break
        token = r.get("NextContinuationToken")

    todo = [(n, p, g) for n, p, g in wanted() if n not in have]
    print("for sale: %d   already in R2: %d   to upload: %d"
          % (len(wanted()), len(have), len(todo)))

    if "--run" not in sys.argv:
        print("\n(dry run — pass --run to upload)")
        return

    for i, (name, path, game) in enumerate(todo, 1):
        s3.upload_file(path, bucket, name, ExtraArgs={
            "ContentType": "image/jpeg",
            # The game rides along so a delivery can be audited later.
            # URL-encoded because S3 metadata is ASCII-only and every one
            # of these names contains an em-dash, which fails validation
            # and aborts the whole upload.
            "Metadata": {"game": quote(game)},
        })
        if i % 20 == 0:
            print("  %d/%d..." % (i, len(todo)))
    print("uploaded %d" % len(todo))


if __name__ == "__main__":
    main()
