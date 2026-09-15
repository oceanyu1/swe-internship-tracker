# Canada SWE Internship Tracker

Watches the [SimplifyJobs/Summer2027-Internships](https://github.com/SimplifyJobs/Summer2027-Internships)
board and messages you when a **new Software Engineering internship in Canada**
is posted. Runs itself on a schedule via GitHub Actions — no server, no cost on a
public repo.

## How it works

1. Every 2 hours, a GitHub Actions job runs `tracker.py`.
2. It downloads the repo's structured `listings.json` and keeps only postings
   that are **Software / Software Engineering**, **currently open**, and have at
   least one **Canadian** location.
3. It compares against `data/seen_ids.json` (its memory) and messages you about
   anything new, then commits the updated memory back to this repo.

The **first run seeds silently** — it records everything already open so you
aren't flooded with the existing backlog. Real alerts begin on the next run.

## Setup (about 5 minutes)

### 1. Create your own repo with these files

Make a **new repository** (public is simplest and free) and add these files:
`tracker.py`, `.github/workflows/track.yml`, `data/.gitkeep`, `.gitignore`.
No secrets live in the code, so a public repo is safe.

### 2. Pick how you want to be messaged, and get the credential

Choose **one** channel:

**Discord (easiest)** — In a Discord server you own: *Server Settings → Integrations
→ Webhooks → New Webhook → Copy Webhook URL.* That URL is all you need.

**Telegram** — Message [@BotFather](https://t.me/BotFather), send `/newbot`, follow
the prompts, and copy the **bot token**. Then send your new bot any message, open
`https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser, and copy the
`chat.id` number — that's your **chat ID**.

**ntfy (phone push, no account)** — Install the ntfy app, pick a hard-to-guess
**topic name** (e.g. `canada-swe-a8f3k2`), and subscribe to it in the app.

### 3. Add repo secrets

In your repo: *Settings → Secrets and variables → Actions → New repository secret.*
Add `NOTIFY_CHANNEL` plus the ones for your channel:

| Channel  | Secrets to add                                            |
|----------|-----------------------------------------------------------|
| Discord  | `NOTIFY_CHANNEL` = `discord`, `DISCORD_WEBHOOK_URL`       |
| Telegram | `NOTIFY_CHANNEL` = `telegram`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| ntfy     | `NOTIFY_CHANNEL` = `ntfy`, `NTFY_TOPIC`                    |

### 4. Enable and test

Open the **Actions** tab (accept the prompt to enable workflows if shown), pick
**Track Canada SWE Internships**, and click **Run workflow**. The first run seeds
memory silently. Run it again to confirm it reports "No new roles," and you're set.

## Customizing

Everything you'd want to change is small:

- **What gets matched** — edit `is_match()` in `tracker.py`. To also catch AI/ML
  roles, change the category check to
  `if not any(c in category for c in ("software", "ai/ml", "data")):`. To restrict
  to specific cities, tighten the location check, e.g.
  `any("toronto" in loc.lower() or "waterloo" in loc.lower() for loc in locations)`.
- **How often** — change the `cron` line in `.github/workflows/track.yml`
  (e.g. `"0 * * * *"` for hourly).
- **Message format** — edit `format_role()`.

## Good to know

- Scheduled Actions can be delayed by a few minutes when GitHub is busy, and are
  auto-disabled after 60 days with **no repo activity** — but every alert commits
  to the repo, which keeps it active, so in practice it stays alive while roles
  are flowing.
- The tracker never overwrites its memory on a failed download, so a temporary
  outage won't cause a flood of repeat alerts afterward.
- The data comes from a community-maintained feed; if its schema ever changes,
  the filter may need a tweak. `tracker.py` prints how many listings matched on
  every run, which makes that easy to spot in the Actions logs.
