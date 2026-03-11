#!/usr/bin/env python3
"""
Plaud API Client - Fetch recordings from your Plaud account

Usage:
    1. Token is loaded automatically from .env file
    2. Run: python plaud_client.py details <file_id>

Or set PLAUD_TOKEN environment variable, or use --token flag.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

import requests
from dotenv import load_dotenv

# Load .env from script directory
load_dotenv(Path(__file__).parent / ".env")


class PlaudClient:
    """Client for interacting with the Plaud API."""

    # Region-specific API domains
    API_DOMAINS = {
        "eu-central-1": "https://api-euc1.plaud.ai",
        "us-east-1": "https://api-use1.plaud.ai",  # Assumed pattern
    }

    def __init__(self, token: str, region: str = "eu-central-1", api_domain: str = None):
        """
        Initialize the Plaud client.

        Args:
            token: Bearer token (with or without 'bearer ' prefix)
            region: AWS region (default: eu-central-1)
            api_domain: Override API domain (from PLAUD_API_DOMAIN env var)
        """
        self.token = token if token.startswith("bearer ") else f"bearer {token}"
        self.api_domain = api_domain or self.API_DOMAINS.get(region, self.API_DOMAINS["eu-central-1"])
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": self.token,
            "Content-Type": "application/json",
        })

    def get_file_details(self, file_id: str) -> dict:
        """
        Get detailed information about a file.

        Args:
            file_id: The 32-character hex file ID

        Returns:
            File details dictionary
        """
        url = f"{self.api_domain}/file/detail/{file_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def download_audio(self, file_id: str, output_path: str = None) -> str:
        """
        Download the audio file (MP3) for a recording.

        Args:
            file_id: The 32-character hex file ID
            output_path: Optional output file path. If not provided,
                        uses the file's name from details.

        Returns:
            Path to the downloaded file
        """
        # Get file details for the name if not provided
        if output_path is None:
            details = self.get_file_details(file_id)
            file_name = details.get("data", {}).get("file_name", file_id)
            # Sanitize filename
            file_name = "".join(c for c in file_name if c.isalnum() or c in " -_").strip()
            output_path = f"{file_name}.mp3"

        url = f"{self.api_domain}/file/download/{file_id}"
        response = self.session.get(url, stream=True)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return output_path

    def get_batch_file_details(self, file_ids: list[str]) -> dict:
        """
        Get details for multiple files at once.

        Args:
            file_ids: List of file IDs

        Returns:
            Dictionary with file details
        """
        url = f"{self.api_domain}/file/list"
        response = self.session.post(url, json=file_ids)
        response.raise_for_status()
        return response.json()

    def list_files(self, include_trash: bool = False) -> list[dict]:
        """
        List all files in the account.

        Args:
            include_trash: Whether to include trashed files

        Returns:
            List of file dictionaries with id, filename, duration, etc.
        """
        url = f"{self.api_domain}/file/simple/web"
        response = self.session.get(url)
        response.raise_for_status()
        data = response.json()

        files = data.get("data_file_list", [])
        if not include_trash:
            files = [f for f in files if not f.get("is_trash", False)]
        return files

    def get_file_tags(self) -> dict:
        """Get all file tags/folders."""
        url = f"{self.api_domain}/filetag/"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_ai_status(self, file_id: str) -> dict:
        """Get AI processing status for a file."""
        url = f"{self.api_domain}/ai/file-task-status"
        response = self.session.get(url, params={"file_ids": file_id})
        response.raise_for_status()
        return response.json()

    def update_file_config(self, file_id: str, language: str = "auto",
                           template: str = "AI-CHOICE", llm: str = "claude-sonnet-4.6",
                           diarization: int = 1) -> dict:
        """
        Update file transcription config (step 1 of transcription flow).

        Args:
            file_id: The 32-character hex file ID
            language: Language code ("auto", "en", "ru", etc.)
            template: Summary template type ("AI-CHOICE" = Adaptive Summary)
            llm: AI model for summary
            diarization: Speaker diarization (1=enabled, 0=disabled)

        Returns:
            API response dictionary
        """
        url = f"{self.api_domain}/file/{file_id}"
        payload = {
            "extra_data": {
                "tranConfig": {
                    "language": language,
                    "type_type": "system",
                    "type": template,
                    "diarization": diarization,
                    "llm": llm,
                }
            }
        }
        response = self.session.patch(url, json=payload)
        response.raise_for_status()
        return response.json()

    def trigger_transcription(self, file_id: str, language: str = "auto",
                              template: str = "AI-CHOICE", llm: str = "claude-sonnet-4.6",
                              diarization: int = 1, is_reload: int = 0) -> dict:
        """
        Trigger transcription + AI summary (step 2 of transcription flow).

        Args:
            file_id: The 32-character hex file ID
            language: Language code ("auto", "en", "ru", etc.)
            template: Summary template type ("AI-CHOICE" = Adaptive Summary)
            llm: AI model for summary
            diarization: Speaker diarization (1=enabled, 0=disabled)
            is_reload: 0 for first transcription, 1 for re-transcription

        Returns:
            API response dictionary
        """
        url = f"{self.api_domain}/ai/transsumm/{file_id}"
        info = json.dumps({
            "language": language,
            "diarization": diarization,
            "llm": llm,
            "timezone": 1,
        })
        payload = {
            "is_reload": is_reload,
            "summ_type": template,
            "summ_type_type": "system",
            "info": info,
            "support_mul_summ": True,
        }
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def transcribe(self, file_id: str, language: str = "auto",
                   template: str = "AI-CHOICE", llm: str = "claude-sonnet-4.6",
                   diarization: int = 1) -> dict:
        """
        Full two-step transcription flow: update config then trigger.

        Args:
            file_id: The 32-character hex file ID
            language: Language code ("auto", "en", "ru", etc.)
            template: Summary template type ("AI-CHOICE" = Adaptive Summary)
            llm: AI model for summary
            diarization: Speaker diarization (1=enabled, 0=disabled)

        Returns:
            Transcription trigger response
        """
        self.update_file_config(file_id, language, template, llm, diarization)
        return self.trigger_transcription(file_id, language, template, llm, diarization)

    def get_trans_status(self) -> dict:
        """Get transcription queue/processing status."""
        url = f"{self.api_domain}/ai/trans-status"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_transcription_quota(self) -> dict:
        """Get remaining transcription quota."""
        url = f"{self.api_domain}/user/stat/transcription/quota"
        response = self.session.get(url, params={"notification": "tag"})
        response.raise_for_status()
        return response.json()

    def get_languages(self) -> dict:
        """Get all supported languages (113 total)."""
        url = f"{self.api_domain}/others/language_list"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_templates(self, language_os: str = "en", scene: int = 1) -> dict:
        """
        Get recently used templates.

        Args:
            language_os: UI language code (default: "en")
            scene: Scene type filter (default: 1)

        Returns:
            API response with template list
        """
        url = f"{self.api_domain}/summary/community/templates/recently_used"
        response = self.session.post(url, json={"language_os": language_os, "scene": scene})
        response.raise_for_status()
        return response.json()

    def get_categories(self, language_os: str = "en") -> dict:
        """
        Get template categories.

        Args:
            language_os: UI language code (default: "en")

        Returns:
            API response with category list
        """
        url = f"{self.api_domain}/summary/community/templates/categorys"
        response = self.session.get(url, params={"language_os": language_os})
        response.raise_for_status()
        return response.json()

    def get_settings(self) -> dict:
        """Get user settings (industry, custom words, language, speaker tagging)."""
        url = f"{self.api_domain}/user/me/settings"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_profile(self) -> dict:
        """Get full user profile with membership info."""
        url = f"{self.api_domain}/user/me"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()


def format_duration(ms: int) -> str:
    """Format milliseconds as human-readable duration."""
    seconds = ms // 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def main():
    parser = argparse.ArgumentParser(
        description="Plaud API Client - Download your recordings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # List all files
    python plaud_client.py list

    # List files as JSON
    python plaud_client.py list --json

    # Get file details
    python plaud_client.py details af9e46896091e31b29775331960e66f9

    # Download a recording
    python plaud_client.py download af9e46896091e31b29775331960e66f9

    # Download to specific path
    python plaud_client.py download af9e46896091e31b29775331960e66f9 -o meeting.mp3

    # Download all files
    python plaud_client.py download-all -o ./recordings

    # Get file tags/folders
    python plaud_client.py tags

    # Transcribe a file (two-step: config + trigger)
    python plaud_client.py transcribe af9e46896091e31b29775331960e66f9

    # Transcribe with options
    python plaud_client.py transcribe af9e46896091e31b29775331960e66f9 --language ru --llm claude-sonnet-4.6

    # Transcribe all untranscribed files
    python plaud_client.py transcribe-all

    # Check transcription quota
    python plaud_client.py quota

    # Check transcription status
    python plaud_client.py status

    # List supported languages
    python plaud_client.py languages

    # List languages as JSON
    python plaud_client.py languages --json

    # List recently used templates
    python plaud_client.py templates

    # List template categories
    python plaud_client.py categories

    # Show user settings
    python plaud_client.py settings

    # Show user profile with membership and quota
    python plaud_client.py profile
"""
    )

    parser.add_argument(
        "--token", "-t",
        default=os.environ.get("PLAUD_TOKEN"),
        help="Bearer token (or set PLAUD_TOKEN env var)"
    )
    parser.add_argument(
        "--region", "-r",
        default="eu-central-1",
        help="AWS region (default: eu-central-1)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List command
    list_parser = subparsers.add_parser("list", help="List all files")
    list_parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    list_parser.add_argument("--include-trash", action="store_true", help="Include trashed files")

    # Details command
    details_parser = subparsers.add_parser("details", help="Get file details")
    details_parser.add_argument("file_id", help="File ID (32-char hex string)")
    details_parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    # Download command
    download_parser = subparsers.add_parser("download", help="Download audio file")
    download_parser.add_argument("file_id", help="File ID (32-char hex string)")
    download_parser.add_argument("--output", "-o", help="Output file path")

    # Download-all command
    download_all_parser = subparsers.add_parser("download-all", help="Download all audio files")
    download_all_parser.add_argument("--output", "-o", default="./plaud_downloads", help="Output directory")
    download_all_parser.add_argument("--include-trash", action="store_true", help="Include trashed files")

    # Tags command
    subparsers.add_parser("tags", help="Get file tags/folders")

    # Transcribe command
    transcribe_parser = subparsers.add_parser("transcribe", help="Transcribe a file (config + trigger)")
    transcribe_parser.add_argument("file_id", help="File ID (32-char hex string)")
    transcribe_parser.add_argument("--language", default="auto", help="Language code (default: auto)")
    transcribe_parser.add_argument("--template", default="AI-CHOICE", help="Summary template (default: AI-CHOICE = Adaptive Summary)")
    transcribe_parser.add_argument("--llm", default="claude-sonnet-4.6", help="AI model (default: claude-sonnet-4.6)")
    transcribe_parser.add_argument("--diarization", type=int, default=1, choices=[0, 1], help="Speaker diarization (default: 1=on)")
    transcribe_parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    # Transcribe-all command
    transcribe_all_parser = subparsers.add_parser("transcribe-all", help="Transcribe all untranscribed files")
    transcribe_all_parser.add_argument("--language", default="auto", help="Language code (default: auto)")
    transcribe_all_parser.add_argument("--template", default="AI-CHOICE", help="Summary template (default: AI-CHOICE)")
    transcribe_all_parser.add_argument("--llm", default="claude-sonnet-4.6", help="AI model (default: claude-sonnet-4.6)")
    transcribe_all_parser.add_argument("--diarization", type=int, default=1, choices=[0, 1], help="Speaker diarization (default: 1=on)")
    transcribe_all_parser.add_argument("--delay", type=float, default=2.0, help="Delay between requests in seconds (default: 2)")
    transcribe_all_parser.add_argument("--dry-run", action="store_true", help="List files that would be transcribed without triggering")
    transcribe_all_parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    # Quota command
    subparsers.add_parser("quota", help="Check transcription quota")

    # Status command
    subparsers.add_parser("status", help="Check transcription processing status")

    # Languages command
    languages_parser = subparsers.add_parser("languages", help="List all supported languages")
    languages_parser.add_argument("--json", "-j", action="store_true", help="Output full JSON (default: compact table)")

    # Templates command
    templates_parser = subparsers.add_parser("templates", help="List recently used templates")
    templates_parser.add_argument("--scene", type=int, default=1, help="Scene type filter (default: 1)")
    templates_parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    # Categories command
    categories_parser = subparsers.add_parser("categories", help="List template categories")
    categories_parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    # Settings command
    settings_parser = subparsers.add_parser("settings", help="Show user settings")
    settings_parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    # Profile command
    profile_parser = subparsers.add_parser("profile", help="Show user profile with membership info")
    profile_parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.token:
        print("Error: Token required. Use --token or set PLAUD_TOKEN env var.")
        print("\nTo get your token:")
        print("1. Open https://web.plaud.ai in Chrome")
        print("2. Open DevTools (F12) > Console")
        print("3. Run: localStorage.getItem('tokenstr')")
        print("4. Copy the token (including 'bearer ' prefix)")
        sys.exit(1)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    api_domain = os.environ.get("PLAUD_API_DOMAIN")
    client = PlaudClient(args.token, args.region, api_domain=api_domain)

    try:
        if args.command == "list":
            files = client.list_files(include_trash=args.include_trash)
            if args.json:
                print(json.dumps(files, indent=2, ensure_ascii=False))
            else:
                print(f"Found {len(files)} files:\n")
                for f in files:
                    duration = format_duration(f.get("duration", 0))
                    trash = " [TRASH]" if f.get("is_trash") else ""
                    print(f"  {f['id']}  {duration:>12}  {f['filename']}{trash}")

        elif args.command == "details":
            details = client.get_file_details(args.file_id)
            if args.json:
                print(json.dumps(details, indent=2, ensure_ascii=False))
            else:
                data = details.get("data", {})
                print(f"File: {data.get('file_name', 'Unknown')}")
                print(f"ID: {data.get('file_id')}")
                print(f"Duration: {format_duration(data.get('duration', 0))}")
                print(f"Start Time: {data.get('start_time')}")
                print(f"Trash: {data.get('is_trash', False)}")
                print(f"Scene: {data.get('scene')}")

        elif args.command == "download":
            print(f"Downloading {args.file_id}...")
            output = client.download_audio(args.file_id, args.output)
            print(f"Saved to: {output}")

        elif args.command == "download-all":
            files = client.list_files(include_trash=args.include_trash)
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)

            print(f"Downloading {len(files)} files to {output_dir}\n")
            for i, f in enumerate(files, 1):
                filename = f["filename"]
                safe_name = "".join(c for c in filename if c.isalnum() or c in " -_").strip()
                output_path = output_dir / f"{safe_name}.mp3"

                if output_path.exists():
                    print(f"[{i}/{len(files)}] Skipped (exists): {safe_name}")
                    continue

                print(f"[{i}/{len(files)}] Downloading: {safe_name}...")
                client.download_audio(f["id"], str(output_path))

            print(f"\nDone! Files saved to {output_dir}")

        elif args.command == "tags":
            tags = client.get_file_tags()
            print(json.dumps(tags, indent=2, ensure_ascii=False))

        elif args.command == "transcribe":
            print(f"Transcribing {args.file_id}...")
            print(f"  Language: {args.language}, Template: {args.template}, LLM: {args.llm}, Diarization: {'on' if args.diarization else 'off'}")
            print(f"  Step 1: Updating file config...")
            client.update_file_config(args.file_id, args.language, args.template, args.llm, args.diarization)
            print(f"  Step 2: Triggering transcription...")
            result = client.trigger_transcription(args.file_id, args.language, args.template, args.llm, args.diarization)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                status = result.get("status", "unknown")
                msg = result.get("msg", "")
                print(f"  Result: status={status}, msg={msg}")
                if status == 0:
                    print("  Transcription triggered successfully. Use 'status' command to check progress.")
                else:
                    print(f"  Warning: unexpected status. Full response: {json.dumps(result)}")

        elif args.command == "transcribe-all":
            files = client.list_files(include_trash=False)
            untranscribed = [f for f in files if not f.get("is_trans", False)]

            if not untranscribed:
                print("All files are already transcribed.")
                sys.exit(0)

            if args.dry_run:
                print(f"Found {len(untranscribed)} untranscribed files (dry run):\n")
                for f in untranscribed:
                    duration = format_duration(f.get("duration", 0))
                    print(f"  {f['id']}  {duration:>12}  {f['filename']}")
                sys.exit(0)

            if args.json:
                results = []

            print(f"Transcribing {len(untranscribed)} files...\n")
            print(f"  Language: {args.language}, Template: {args.template}, LLM: {args.llm}, Diarization: {'on' if args.diarization else 'off'}\n")

            for i, f in enumerate(untranscribed, 1):
                file_id = f["id"]
                filename = f["filename"]
                print(f"[{i}/{len(untranscribed)}] {filename} ({file_id})...")
                try:
                    result = client.transcribe(file_id, args.language, args.template, args.llm, args.diarization)
                    status = result.get("status", "unknown")
                    msg = result.get("msg", "")
                    print(f"  -> status={status}, msg={msg}")
                    if args.json:
                        results.append({"file_id": file_id, "filename": filename, "result": result})
                except requests.HTTPError as e:
                    print(f"  -> ERROR: {e.response.status_code} - {e.response.text}")
                    if args.json:
                        results.append({"file_id": file_id, "filename": filename, "error": str(e)})

                if i < len(untranscribed):
                    time.sleep(args.delay)

            if args.json:
                print("\n" + json.dumps(results, indent=2, ensure_ascii=False))

            print(f"\nDone! Triggered transcription for {len(untranscribed)} files.")

        elif args.command == "quota":
            quota = client.get_transcription_quota()
            print(json.dumps(quota, indent=2, ensure_ascii=False))

        elif args.command == "status":
            status = client.get_trans_status()
            print(json.dumps(status, indent=2, ensure_ascii=False))

        elif args.command == "languages":
            data = client.get_languages()
            lang_list = data.get("data", {}).get("default_language_list", {})
            if args.json:
                print(json.dumps(lang_list, indent=2, ensure_ascii=False))
            else:
                print(f"Supported languages ({len(lang_list)}):\n")
                print(f"  {'Code':<12} {'Language':<30} {'Native Name'}")
                print(f"  {'----':<12} {'--------':<30} {'-----------'}")
                for code, info in sorted(lang_list.items()):
                    translate = info.get("translate_content", "")
                    ori = info.get("ori_content", "")
                    display_ori = f"  ({ori})" if ori != translate else ""
                    print(f"  {code:<12} {translate:<30} {ori}")

        elif args.command == "templates":
            data = client.get_templates(scene=args.scene)
            templates = data.get("data", [])
            if args.json:
                print(json.dumps(templates, indent=2, ensure_ascii=False))
            else:
                print(f"Recently used templates (scene={args.scene}):\n")
                for t in templates:
                    ttype = t.get("type", "unknown")
                    tmpl = t.get("template", {})
                    if ttype == "official":
                        tid = tmpl.get("type", "?")
                        tname = tmpl.get("name", "?")
                        desc = tmpl.get("description_short", "")
                    else:
                        ver = tmpl.get("latest_published_version") or tmpl.get("translated_published_version") or {}
                        tid = tmpl.get("id") or ver.get("template_id", "?")
                        tname = ver.get("title", "?")
                        desc = ver.get("description_short", "")
                    print(f"  [{ttype:<10}] {tid:<35} {tname}")
                    if desc:
                        print(f"               {'':35} {desc}")

        elif args.command == "categories":
            data = client.get_categories()
            cats = data.get("data", [])
            if args.json:
                print(json.dumps(cats, indent=2, ensure_ascii=False))
            else:
                print(f"Template categories ({len(cats)}):\n")
                for c in cats:
                    print(f"  {c.get('category_id', '?'):<30} {c.get('category', '?')}")

        elif args.command == "settings":
            data = client.get_settings()
            settings = data.get("data", {})
            if args.json:
                print(json.dumps(settings, indent=2, ensure_ascii=False))
            else:
                print("User Settings:\n")
                print(f"  Industry:             {settings.get('industry', 'not set')}")
                print(f"  Language:             {settings.get('language', 'not set')}")
                print(f"  Auto Speaker Tagging: {settings.get('auto_speaker_tagging', 'unknown')}")
                print(f"  Speaker Cloud:        {settings.get('speaker_cloud_enabled', 'unknown')}")
                words = settings.get("words", "")
                if words:
                    print(f"  Custom Vocabulary:    {words}")
                else:
                    print(f"  Custom Vocabulary:    (none)")

        elif args.command == "profile":
            data = client.get_profile()
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                user = data.get("data_user", {})
                state = data.get("data_state", {})
                print("User Profile:\n")
                print(f"  Name:            {user.get('nickname', 'unknown')}")
                print(f"  Country:         {user.get('user_area_name', user.get('country', 'unknown'))}")
                print(f"  User ID:         {user.get('id', 'unknown')}")
                membership = state.get("membership_type", "unknown")
                flag = state.get("membership_flag", "")
                subscribed = state.get("is_subscribed", False)
                platform = state.get("membership_payment_platform", "")
                status_str = "active" if subscribed else "inactive"
                print(f"  Membership:      {membership} / {flag} ({status_str}, {platform})")
                print(f"  Currency:        {state.get('stripe_currency', '?')} ({state.get('stripe_region', '?')})")

                seconds_left = user.get("seconds_left", 0)
                seconds_total = user.get("seconds_total", 0)
                if seconds_total > 0:
                    hours_left = seconds_left / 3600
                    hours_total = seconds_total / 3600
                    pct = (seconds_left / seconds_total) * 100
                    print(f"\n  Quota:           {hours_left:.0f}h / {hours_total:.0f}h ({pct:.1f}% remaining)")
                    if membership == "unlimited":
                        print(f"                   (unlimited plan — quota is effectively infinite)")
                else:
                    print(f"\n  Quota:           {seconds_left}s left / {seconds_total}s total")

    except requests.HTTPError as e:
        print(f"API Error: {e.response.status_code} - {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
