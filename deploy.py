#!/usr/bin/env python3
"""
Arcade MCP Deployer - Bulk deploy MCPs for all toolkits.

Usage:
    python deploy.py           # Deploy all MCPs
    python deploy.py --dry-run # Preview without deploying
"""

import argparse
import csv
import os
import sys
import time
from collections import defaultdict

import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_KEY = os.getenv("ARCADE_API_KEY")
ORG_ID = os.getenv("ARCADE_ORG_ID")
PROJECT_ID = os.getenv("ARCADE_PROJECT_ID")
BASE_URL = os.getenv("ARCADE_BASE_URL", "https://api.arcade.dev/v1")
SLUG_PREFIX = os.getenv("GATEWAY_SLUG_PREFIX", "")
DELAY = 10  # Fixed 10s delay between API calls to prevent rate limiting


def validate_config():
    missing = [k for k, v in [
        ("ARCADE_API_KEY", API_KEY),
        ("ARCADE_ORG_ID", ORG_ID),
        ("ARCADE_PROJECT_ID", PROJECT_ID)
    ] if not v]
    if missing:
        print(f"Missing required env vars: {', '.join(missing)}")
        print("Copy .env.example to .env and configure values.")
        sys.exit(1)


def api_headers():
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def fetch_tools():
    """Fetch all tools with pagination."""
    tools, offset, limit = [], 0, 100
    while True:
        url = f"{BASE_URL}/orgs/{ORG_ID}/projects/{PROJECT_ID}/tools"
        resp = requests.get(url, headers=api_headers(), params={"limit": limit, "offset": offset})
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        tools.extend(items)
        total = data.get("total_count", len(items))
        print(f"  Fetched {len(tools)}/{total} tools")
        if len(tools) >= total or len(items) < limit:
            break
        offset += limit
    return tools


def group_by_toolkit(tools):
    """Group tools by toolkit name."""
    toolkits = defaultdict(lambda: {"description": "", "tools": []})
    for tool in tools:
        tk = tool.get("toolkit", {})
        if name := tk.get("name"):
            toolkits[name]["description"] = tk.get("description", "")
            toolkits[name]["tools"].append(tool.get("qualified_name"))
    return dict(toolkits)


def get_existing_slugs():
    """Get existing MCP slugs."""
    try:
        url = f"{BASE_URL}/orgs/{ORG_ID}/projects/{PROJECT_ID}/gateways"
        resp = requests.get(url, headers=api_headers())
        resp.raise_for_status()
        return {g.get("slug", "").lower() for g in resp.json().get("items", [])}
    except Exception:
        return set()


def make_slug(name):
    slug = name.lower().replace(" ", "-").replace("_", "-")
    return f"{SLUG_PREFIX}-{slug}" if SLUG_PREFIX else slug


def deploy_mcp(name, info):
    """Deploy a single MCP."""
    url = f"{BASE_URL}/orgs/{ORG_ID}/projects/{PROJECT_ID}/gateways"
    slug = make_slug(name)
    payload = {
        "name": f"{name} MCP",
        "description": info["description"] or f"MCP for {name}",
        "slug": slug,
        "status": "active",
        "auth_type": "arcade",
        "tool_filter": {"allowed_tools": info["tools"]}
    }
    resp = requests.post(url, headers=api_headers(), json=payload)
    return resp, slug


def main():
    parser = argparse.ArgumentParser(description="Deploy Arcade MCPs for all toolkits")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deploying")
    args = parser.parse_args()

    validate_config()

    print(f"Org: {ORG_ID} | Project: {PROJECT_ID}" + (f" | Prefix: {SLUG_PREFIX}" if SLUG_PREFIX else ""))
    if args.dry_run:
        print("DRY RUN - No MCPs will be deployed\n")

    # Fetch and group tools
    print("\nFetching tools...")
    tools = fetch_tools()
    toolkits = group_by_toolkit(tools)
    print(f"Found {len(toolkits)} toolkits\n")

    existing = get_existing_slugs()
    results = []
    deployed, skipped, failed = 0, 0, 0

    for i, (name, info) in enumerate(sorted(toolkits.items()), 1):
        slug = make_slug(name)
        tool_count = len(info["tools"])

        if slug in existing:
            print(f"[{i}/{len(toolkits)}] SKIP {name}")
            skipped += 1
            continue

        if args.dry_run:
            print(f"[{i}/{len(toolkits)}] WOULD DEPLOY {name} ({tool_count} tools) → {slug}")
            deployed += 1
            results.append({"mcp": name, "description": info["description"][:200], "url": f"https://api.arcade.dev/mcp/{slug}", "num_tools": tool_count})
            continue

        print(f"[{i}/{len(toolkits)}] DEPLOY {name} ({tool_count} tools)...", end=" ", flush=True)
        try:
            resp, slug = deploy_mcp(name, info)
            if resp.status_code in [200, 201]:
                actual_slug = resp.json().get("slug", slug)
                print(f"✓ {actual_slug}")
                deployed += 1
                results.append({"mcp": name, "description": info["description"][:200], "url": f"https://api.arcade.dev/mcp/{actual_slug}", "num_tools": tool_count})
            else:
                error = resp.json().get("message", resp.text)[:50]
                print(f"✗ {error}")
                failed += 1
        except Exception as e:
            print(f"✗ {str(e)[:50]}")
            failed += 1

        if i < len(toolkits) and not args.dry_run:
            time.sleep(DELAY)

    # Summary
    print(f"\nDone: {deployed} deployed, {skipped} skipped, {failed} failed")

    if results:
        csv_file = "deployed_mcps.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["mcp", "description", "url", "num_tools"])
            writer.writeheader()
            writer.writerows(results)
        print(f"Saved to {csv_file}")


if __name__ == "__main__":
    main()
