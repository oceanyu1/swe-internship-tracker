#!/usr/bin/env python3
"""
Canada SWE Internship Tracker
=============================
Watches the SimplifyJobs/Summer2027-Internships job board and notifies you
when NEW Software Engineering internship roles in Canada appear.

Design notes:
- Standard library only (no `pip install`) so it runs on a bare GitHub
  Actions Python step.
- Reads the repo's structured listings.json rather than scraping the README.
- Uses data/seen_ids.json as its memory, committed back to the repo by the
  workflow, so you only ever get told about a role once.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

FEED_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/"
    "Summer2027-Internships/dev/.github/scripts/listings.json"
)
STATE_FILE = os.path.join("data", "seen_ids.json")

# If more than this many new roles show up at once, send a compact digest
# instead of one message per role (avoids a wall of notifications).
MAX_INDIVIDUAL = 12


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------
def fetch_listings():
    req = urllib.request.Request(
        FEED_URL, headers={"User-Agent": "canada-swe-intern-tracker"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


# ---------------------------------------------------------------------------
# Filter  —  edit is_match() to change what you get pinged about
# ---------------------------------------------------------------------------
def is_match(listing):
    # Category: "Software" and "Software Engineering" both contain "software".
    # (AI/ML/Data, Hardware, Quant, Product are excluded.)
    category = (listing.get("category") or "").lower()
    if "software" not in category:
        return False

    # Only currently-open, visible postings.
    if not (listing.get("active") and listing.get("is_visible")):
        return False

    # At least one Canadian location. Every Canadian location string in the
    # feed contains "Canada" (e.g. "Toronto, ON, Canada", "Remote in Canada").
    locations = listing.get("locations") or []
    if not any("canada" in (loc or "").lower() for loc in locations):
        return False

    return True


# ---------------------------------------------------------------------------
# State (dedup memory)
# ---------------------------------------------------------------------------
def load_seen():
    try:
        with open(STATE_FILE) as f:
            return set(json.load(f))
    except FileNotFoundError:
        return None  # signals a first run -> seed instead of flooding you
    except (json.JSONDecodeError, ValueError):
        return set()


def save_seen(ids):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(ids), f, indent=0)


# ---------------------------------------------------------------------------
# Message formatting
# ---------------------------------------------------------------------------
def format_role(listing):
    company = listing.get("company_name", "Unknown company")
    title = listing.get("title", "Software Engineering Intern")
    locs = ", ".join(listing.get("locations", [])) or "Canada"
    url = listing.get("url", "")
    return f"\U0001f341 {company} \u2014 {title}\n\U0001f4cd {locs}\n\U0001f517 {url}"


# ---------------------------------------------------------------------------
# Notifications  —  choose one with the NOTIFY_CHANNEL secret
# ---------------------------------------------------------------------------
def _post(url, data, headers=None):
    body = data if isinstance(data, bytes) else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers=headers or {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status


def send_discord(chunks):
    webhook = os.environ["DISCORD_WEBHOOK_URL"]
    for chunk in chunks:
        _post(webhook, {"content": chunk})
        time.sleep(1)


def send_telegram(chunks):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in chunks:
        _post(
            url,
            {"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
        )
        time.sleep(1)


def send_ntfy(chunks):
    topic = os.environ["NTFY_TOPIC"]
    url = f"https://ntfy.sh/{topic}"
    for chunk in chunks:
        _post(
            url,
            chunk.encode("utf-8"),
            headers={
                "Title": "New Canada SWE internship",
                "Content-Type": "text/plain; charset=utf-8",
            },
        )
        time.sleep(1)


CHANNELS = {"discord": send_discord, "telegram": send_telegram, "ntfy": send_ntfy}
CHAR_LIMITS = {"discord": 1900, "telegram": 3800, "ntfy": 3800}


def chunk_messages(blocks, limit):
    """Pack role blocks into as few messages as fit under the channel limit."""
    chunks, cur = [], ""
    for b in blocks:
        if cur and len(cur) + len(b) + 2 > limit:
            chunks.append(cur)
            cur = ""
        cur = b if not cur else cur + "\n\n" + b
    if cur:
        chunks.append(cur)
    return chunks


def notify(new_listings):
    channel = os.environ.get("NOTIFY_CHANNEL", "").lower().strip()
    if channel not in CHANNELS:
        print(f"[warn] NOTIFY_CHANNEL '{channel}' not set/recognized; printing instead.")
        for listing in new_listings:
            print(format_role(listing))
            print()
        return

    count = len(new_listings)
    plural = "s" if count != 1 else ""
    header = f"\U0001f1e8\U0001f1e6 {count} new Software Engineering internship{plural} in Canada"

    if count <= MAX_INDIVIDUAL:
        blocks = [header] + [format_role(l) for l in new_listings]
    else:
        lines = [
            f"\u2022 {l.get('company_name', '?')} \u2014 {l.get('title', '?')}  {l.get('url', '')}"
            for l in new_listings
        ]
        blocks = [header] + lines

    chunks = chunk_messages(blocks, CHAR_LIMITS[channel])
    CHANNELS[channel](chunks)
    print(f"[ok] Sent {count} new role(s) via {channel}.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    try:
        listings = fetch_listings()
    except (urllib.error.URLError, ValueError, json.JSONDecodeError) as e:
        # Never overwrite state on a failed fetch.
        print(f"[error] Could not fetch/parse feed: {e}", file=sys.stderr)
        sys.exit(1)

    matched = [l for l in listings if is_match(l)]
    matched_ids = {l["id"] for l in matched}
    all_feed_ids = {l.get("id") for l in listings}
    print(f"[info] {len(listings)} total listings; {len(matched)} match SWE + Canada + open.")

    seen = load_seen()

    if seen is None:
        # First run: record everything currently open so you aren't flooded
        # with the entire existing backlog. Real alerts start next run.
        save_seen(matched_ids)
        print(f"[info] First run \u2014 seeded {len(matched_ids)} existing roles, no alerts sent.")
        return

    new_listings = [l for l in matched if l["id"] not in seen]
    if new_listings:
        new_listings.sort(key=lambda l: l.get("date_posted", 0), reverse=True)
        notify(new_listings)
    else:
        print("[info] No new roles this run.")

    # Keep every seen id that's still anywhere in the feed (keeps the file
    # bounded and avoids re-alerting if a role's active flag briefly flaps),
    # and add the current matches.
    updated = (seen | matched_ids) & all_feed_ids
    save_seen(updated)


if __name__ == "__main__":
    main()
