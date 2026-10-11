#!/usr/bin/env python3
"""
Utility script to set all public GitHub repositories for ilyamiro to private.
Requires a GitHub Personal Access Token with 'repo' scope.
"""

import json
import sys
import urllib.error
import urllib.request

def main():
    if len(sys.argv) > 1:
        token = sys.argv[1].strip()
    else:
        token = input("Enter your GitHub Personal Access Token (PAT): ").strip()

    if not token:
        print("❌ Error: GitHub Token is required.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Repo-Privacy-Script",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Fetch authenticated user profile
    try:
        user_req = urllib.request.Request("https://api.github.com/user", headers=headers)
        with urllib.request.urlopen(user_req) as resp:
            user_data = json.loads(resp.read().decode())
            username = user_data.get("login")
            print(f"👤 Authenticated as: {username}")
    except Exception as e:
        print(f"❌ Failed to verify GitHub token: {e}")
        sys.exit(1)

    # Fetch all user repos
    print(f"🔍 Fetching repositories for user '{username}'...")
    req = urllib.request.Request(
        "https://api.github.com/user/repos?per_page=100&type=owner",
        headers=headers,
    )

    try:
        with urllib.request.urlopen(req) as resp:
            repos = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"❌ Failed to fetch repositories (HTTP {e.code}): {e.read().decode()}")
        sys.exit(1)

    public_repos = [r for r in repos if not r.get("private")]

    if not public_repos:
        print("✅ All repositories are already private!")
        return

    print(f"📦 Found {len(public_repos)} public repositories to hide:")
    for r in public_repos:
        print(f"  - {r['name']}")

    print("\n🔒 Converting repositories to private...")
    for r in public_repos:
        repo_name = r["name"]
        patch_url = f"https://api.github.com/repos/{username}/{repo_name}"
        patch_data = json.dumps({"private": True}).encode()

        patch_req = urllib.request.Request(
            patch_url,
            data=patch_data,
            headers=headers,
            method="PATCH",
        )

        try:
            with urllib.request.urlopen(patch_req) as p_resp:
                if p_resp.status == 200:
                    print(f"  ✅ [PRIVATE] {repo_name}")
                else:
                    print(f"  ⚠️ {repo_name}: Status {p_resp.status}")
        except urllib.error.HTTPError as pe:
            print(f"  ❌ Error for {repo_name} (HTTP {pe.code}): {pe.read().decode()}")

    print("\n🎉 Completed! All selected repositories have been converted to private.")


if __name__ == "__main__":
    main()
