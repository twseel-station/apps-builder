#!/usr/bin/env python3
"""Helpers shared by every mobile pipeline.

    defines      resolve <PREFIX>_<KEY>_<SUFFIX> secrets into a --dart-define-from-file json
    version      read pubspec version, bump the build number past what Google Play already has
    play-upload  push an .aab to a Play track
    testflight   push an .ipa to TestFlight (if the build produced one)
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys


def set_output(key, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as fh:
            fh.write(f"{key}={value}\n")
    print(f"  -> {key}={value}")


# ---------------------------------------------------------------- defines
def cmd_defines(args):
    secrets = json.loads(os.environ["ALL_SECRETS"])
    prefix, suffix = os.environ["PREFIX"], os.environ["SUFFIX"]
    keys = [
        k.strip()
        for k in os.environ["KEYS"].splitlines()
        if k.strip() and not k.strip().startswith("#")
    ]
    resolved, missing = {"APP_ENV": os.environ["APP_ENV"]}, []

    for key in keys:
        secret_name = f"{prefix}_{key}_{suffix}"
        value = secrets.get(secret_name, "")
        if not value:
            missing.append(secret_name)
            continue
        print(f"::add-mask::{value}")
        resolved[key] = value
        print(f"  {key:<22} <- secrets.{secret_name}")

    if missing:
        print(f"::error::Missing GitHub secrets: {', '.join(missing)}")
        sys.exit(1)

    with open(args.out, "w") as fh:
        json.dump(resolved, fh)
    os.chmod(args.out, 0o600)


# ---------------------------------------------------------------- google play
def play_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_info(
        json.loads(os.environ["PLAY_JSON"]),
        scopes=["https://www.googleapis.com/auth/androidpublisher"],
    )
    return build("androidpublisher", "v3", credentials=creds, cache_discovery=False)


def cmd_version(args):
    with open(args.pubspec) as fh:
        match = re.search(r"^version:\s*([\w.\-]+)(?:\+(\d+))?", fh.read(), re.M)
    name, code = match.group(1), int(match.group(2) or 1)

    if args.play_package and os.environ.get("PLAY_JSON"):
        svc = play_service()
        edit = svc.edits().insert(packageName=args.play_package, body={}).execute()
        bundles = (
            svc.edits()
            .bundles()
            .list(packageName=args.play_package, editId=edit["id"])
            .execute()
            .get("bundles", [])
        )
        svc.edits().delete(packageName=args.play_package, editId=edit["id"]).execute()
        highest = max((b["versionCode"] for b in bundles), default=0)
        if code <= highest:
            print(f"pubspec build {code} already on Play (highest {highest}) -> bumping")
            code = highest + 1

    set_output("name", name)
    set_output("code", code)


def cmd_play_upload(args):
    svc = play_service()
    pkg = args.package
    edit_id = svc.edits().insert(packageName=pkg, body={}).execute()["id"]

    from googleapiclient.http import MediaFileUpload

    uploaded = (
        svc.edits()
        .bundles()
        .upload(
            packageName=pkg,
            editId=edit_id,
            media_body=MediaFileUpload(args.bundle, mimetype="application/octet-stream"),
        )
        .execute()
    )
    code = str(uploaded["versionCode"])
    releases = [{"name": args.name, "versionCodes": [code], "status": args.status}]

    if args.status == "draft":
        # a draft must not wipe the release users are on right now
        current = svc.edits().tracks().get(packageName=pkg, editId=edit_id, track=args.track).execute()
        releases += [r for r in current.get("releases", []) if r.get("status") != "draft"]

    svc.edits().tracks().update(
        packageName=pkg, editId=edit_id, track=args.track, body={"releases": releases}
    ).execute()
    svc.edits().commit(packageName=pkg, editId=edit_id).execute()
    print(f"Play: {pkg} versionCode {code} -> track '{args.track}' ({args.status})")
    set_output("code", code)


# ---------------------------------------------------------------- testflight
def cmd_testflight(args):
    key_id, issuer = os.environ.get("APPLE_KEY_ID"), os.environ.get("APPLE_ISSUER_ID")
    key_path = os.path.expanduser(f"~/.appstoreconnect/private_keys/AuthKey_{key_id}.p8")
    ipas = glob.glob(os.path.join(args.ipa_dir, "*.ipa"))

    if not (key_id and issuer and os.path.exists(key_path)):
        print("::warning::Apple API key not configured, skipping TestFlight.")
        return set_output("uploaded", "false")
    if not ipas:
        print("::warning::No signed .ipa produced (build ran with --no-codesign), nothing to upload.")
        return set_output("uploaded", "false")

    code = subprocess.call(
        ["xcrun", "altool", "--upload-app", "-f", ipas[0], "-t", "ios",
         "--apiKey", key_id, "--apiIssuer", issuer]
    )
    set_output("uploaded", "true" if code == 0 else "false")
    sys.exit(code)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("defines")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_defines)

    p = sub.add_parser("version")
    p.add_argument("--pubspec", required=True)
    p.add_argument("--play-package", default="")
    p.set_defaults(fn=cmd_version)

    p = sub.add_parser("play-upload")
    p.add_argument("--package", required=True)
    p.add_argument("--bundle", required=True)
    p.add_argument("--track", required=True)
    p.add_argument("--status", default="completed")
    p.add_argument("--name", required=True)
    p.set_defaults(fn=cmd_play_upload)

    p = sub.add_parser("testflight")
    p.add_argument("--ipa-dir", required=True)
    p.set_defaults(fn=cmd_testflight)

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
