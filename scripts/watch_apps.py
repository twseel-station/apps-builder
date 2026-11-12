#!/usr/bin/env python3
"""Poll the private app repos and start a build when the newest commit asks for one.

Commit tags (anywhere in the message):
    [android] [play] [apk]    -> android
    [ios] [testflight]        -> ios
    [both]                    -> android + ios
develop -> test environment, main -> production.

A commit is built once: we stamp it with the git tag  ab/<env>/<sha7>  in the app repo.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

ORG = "twseel-station"
APPS = ["client-app", "restaurant-app", "delivery-app"]
BRANCH_ENV = {"develop": "test", "main": "production"}
PAT, GH = os.environ["GH_PAT"], os.environ["GITHUB_TOKEN"]
BUILDER = os.environ.get("GITHUB_REPOSITORY", f"{ORG}/apps-builder")


def api(method, url, token, body=None):
    req = urllib.request.Request(
        url if url.startswith("http") else f"https://api.github.com{url}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as err:
        return err.code, {}


def platform_of(message):
    msg = message.lower()
    if "[both]" in msg:
        return "both"
    if any(t in msg for t in ("[android]", "[play]", "[apk]")):
        return "android"
    if any(t in msg for t in ("[ios]", "[testflight]")):
        return "ios"
    return None


def main():
    started = 0
    for app in APPS:
        for branch, env in BRANCH_ENV.items():
            status, commit = api("GET", f"/repos/{ORG}/{app}/commits/{branch}", PAT)
            if status != 200:
                print(f"{app}/{branch}: cannot read ({status})")
                continue
            sha, message = commit["sha"], commit["commit"]["message"]
            platform = platform_of(message)
            if not platform:
                continue

            tag = f"ab/{env}/{sha[:7]}"
            if api("GET", f"/repos/{ORG}/{app}/git/ref/tags/{tag}", PAT)[0] == 200:
                continue  # already built

            api("POST", f"/repos/{ORG}/{app}/git/refs", PAT, {"ref": f"refs/tags/{tag}", "sha": sha})
            status, _ = api(
                "POST",
                f"/repos/{BUILDER}/actions/workflows/{app}.yml/dispatches",
                GH,
                {"ref": "main", "inputs": {"env": env, "platform": platform, "ref": sha}},
            )
            if status != 204:
                api("DELETE", f"/repos/{ORG}/{app}/git/refs/tags/{tag}", PAT)
                print(f"::error::dispatch failed for {app} ({status})")
                sys.exit(1)
            print(f"started {app} {env} {platform} @ {sha[:7]}")
            started += 1
    print(f"done, {started} build(s) started")


if __name__ == "__main__":
    main()
