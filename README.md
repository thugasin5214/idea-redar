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