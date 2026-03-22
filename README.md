# Idea Radar 🔭

Daily digest of Reddit + Indie Hackers discussions about side projects, pain points, and startup ideas.

## Setup

1. Install: `pip install -e .`
2. Copy config: `cp config.example.yaml config.yaml`
3. Fill in config.yaml (Reddit API keys, OpenRouter key, Gmail credentials)
4. Run: `python scripts/run_daily.py`

## Reddit API Setup
- Go to https://www.reddit.com/prefs/apps
- Create a "script" app
- Copy client_id and client_secret to config.yaml

## Gmail Setup
- Enable 2FA on Gmail
- Create an App Password at https://myaccount.google.com/apppasswords
- Use App Password in config.yaml (not your regular password)

## Config
See config.example.yaml for all options.

## GitHub Actions Setup (Automated Daily Digest)

1. Push this repo to GitHub
2. Go to **Settings → Secrets and variables → Actions → New repository secret**
3. Add these secrets:

| Secret | Value |
|--------|-------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key (sk-or-...) |
| `GMAIL_SENDER` | Your Gmail address |
| `GMAIL_PASSWORD` | Gmail App Password (16-char, not your login password) |
| `GMAIL_RECIPIENT` | Where to send the digest |
| `REDDIT_CLIENT_ID` | (optional) Reddit app client ID |
| `REDDIT_CLIENT_SECRET` | (optional) Reddit app client secret |
| `AI_MODEL` | (optional) Default: `openai/gpt-4o-mini:free` |
| `AI_FALLBACK_MODEL` | (optional) Default: `google/gemini-flash-1.5:free` |

4. The workflow runs daily at **8:00 AM Toronto time (EDT)**
5. To trigger manually: Go to **Actions → Daily Idea Radar Digest → Run workflow**

### Customizing channels and prompt
Edit `config.example.yaml` in the repo to change subreddits, keywords, AI prompt focus, etc.
These non-sensitive settings are committed to the repo and used as the base config.