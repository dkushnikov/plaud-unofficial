# Plaud API Claude Skill

A self-contained Claude Code skill for accessing Plaud voice recorder data: recordings, transcripts, AI summaries, transcription triggers, and account management.

## Contents

| File | Purpose |
|------|---------|
| `SKILL.md` | Main skill document with credential tutorial |
| `plaud_client.py` | CLI tool for all Plaud API operations |
| `PLAUD_API.md` | Detailed API documentation (15+ endpoints) |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for credentials |

## Commands

| Command | Description |
|---------|-------------|
| `list` | List all recordings |
| `details <id>` | Get file details with transcript and AI summary |
| `download <id>` | Download audio file (MP3) |
| `download-all` | Download all audio files |
| `tags` | Get file tags/folders |
| `transcribe <id>` | Trigger transcription + AI summary for a file |
| `transcribe-all` | Transcribe all untranscribed files (`--dry-run` supported) |
| `quota` | Check transcription quota |
| `status` | Check transcription processing status |
| `languages` | List 113 supported languages |
| `templates` | List recently used templates (official + community) |
| `categories` | List 15 template categories |
| `settings` | Show user settings (industry, vocabulary, speaker tagging) |
| `profile` | Show user profile with membership and quota info |

## Installation

### Option 1: Symlink (Recommended for Development)

```bash
ln -s /path/to/plaud-unofficial ~/.claude/skills/plaud-api
```

### Option 2: Copy

```bash
cp -r /path/to/plaud-unofficial ~/.claude/skills/plaud-api
```

## Quick Setup

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

3. Follow the credential tutorial in `SKILL.md` to obtain your Plaud API token from `localStorage` in the web app

4. Update `.env` with your actual credentials

5. Test with:
   ```bash
   python3 plaud_client.py list
   ```

## Usage in Claude Code

Invoke with:
- `/plaud-api` - Full skill with setup tutorial
- `/plaud` - Alias
- `/plaud-recordings` - Alias

## API Endpoints

The skill documents 15+ API endpoints reverse-engineered from the Plaud web app, including:

- **File operations**: list, details, download, batch details
- **Transcription**: config update (PATCH), trigger (POST), status, quota
- **Languages**: 113 supported languages with codes
- **Templates**: official + community templates, 15 categories
- **Account**: user profile, settings, membership info
- **Sharing**: private and public share endpoints

See `PLAUD_API.md` for full documentation.

## Requirements

- Python 3.x
- `requests` and `python-dotenv` packages (see requirements.txt)
- Plaud account with web access at https://web.plaud.ai
