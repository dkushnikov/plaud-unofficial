#!/usr/bin/env python3
"""
Plaud Sync — download all Plaud recordings (transcript + summary + audio)
into an Obsidian-friendly folder structure.

Usage:
    python3 plaud_sync.py                      # sync new files only
    python3 plaud_sync.py --output /path/to   # custom output dir
    python3 plaud_sync.py --no-audio           # skip audio downloads
    python3 plaud_sync.py --force              # re-download existing
"""

import argparse
import gzip
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load .env from script directory
load_dotenv(Path(__file__).parent / ".env")

from plaud_client import PlaudClient, format_duration


def sanitize_filename(name: str) -> str:
    """Remove characters unsafe for filenames, keep unicode."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.strip('. ')
    return name[:200]  # cap length


def download_s3_content(url: str) -> bytes:
    """Download from pre-signed S3 URL, handle gzip."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    try:
        return gzip.decompress(resp.content)
    except (gzip.BadGzipFile, OSError):
        return resp.content


def format_timestamp(ms: int) -> str:
    """Format milliseconds as MM:SS or HH:MM:SS."""
    seconds = ms // 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def segments_to_markdown(segments: list) -> str:
    """Convert transcript segments to readable markdown."""
    lines = []
    current_speaker = None
    for seg in segments:
        speaker = seg.get('speaker', 'Unknown')
        content = seg.get('content', '').strip()
        timestamp = format_timestamp(seg.get('start_time', 0))
        if not content:
            continue
        if speaker != current_speaker:
            current_speaker = speaker
            lines.append(f"\n**{speaker}** ({timestamp})")
        else:
            lines.append(f"({timestamp})")
        lines.append(content)
    return '\n'.join(lines)


def sync_file(client: PlaudClient, file_info: dict, output_dir: Path,
              download_audio: bool = True, force: bool = False) -> bool:
    """
    Download transcript, summary, and audio for one file.
    Returns True if new content was downloaded.
    """
    file_id = file_info['id']
    filename = file_info.get('filename', file_id)
    duration_ms = file_info.get('duration', 0)

    # Parse date from filename (e.g., "03-07 Title")
    date_match = re.match(r'(\d{2}-\d{2})\s', filename)
    if date_match:
        folder_name = sanitize_filename(filename)
    else:
        # Use start_time if available
        start_ts = file_info.get('start_time', 0)
        if start_ts:
            dt = datetime.fromtimestamp(start_ts / 1000)
            prefix = dt.strftime('%m-%d')
            folder_name = sanitize_filename(f"{prefix} {filename}")
        else:
            folder_name = sanitize_filename(filename)

    file_dir = output_dir / folder_name

    # Check if already synced
    transcript_path = file_dir / "transcript.md"
    if transcript_path.exists() and not force:
        return False

    # Get full details (includes pre-signed S3 URLs)
    details = client.get_file_details(file_id)
    data = details.get('data', {})

    file_dir.mkdir(parents=True, exist_ok=True)

    # Parse start time
    start_ts = data.get('start_time', 0)
    if start_ts:
        dt = datetime.fromtimestamp(start_ts / 1000)
        recorded_date = dt.strftime('%Y-%m-%d')
        recorded_time = dt.strftime('%H:%M')
    else:
        recorded_date = ''
        recorded_time = ''

    # Download content from S3
    transcript_text = ''
    summary_text = ''
    outline_text = ''

    for item in data.get('content_list', []):
        url = item.get('data_link', '')
        dtype = item.get('data_type', '')
        if not url:
            continue

        try:
            content = download_s3_content(url)
            text = content.decode('utf-8')

            if dtype == 'transaction':
                segments = json.loads(text)
                if isinstance(segments, list):
                    transcript_text = segments_to_markdown(segments)
                    # Count unique speakers
                    speakers = set(s.get('speaker', '') for s in segments)
                    speakers.discard('')
                elif isinstance(segments, dict):
                    segs = segments.get('segments', [])
                    transcript_text = segments_to_markdown(segs)
                    speakers = set(s.get('speaker', '') for s in segs)
                    speakers.discard('')

            elif dtype == 'auto_sum_note':
                summary_text = text

            elif dtype == 'outline':
                outline_data = json.loads(text)
                if isinstance(outline_data, list):
                    topics = [f"- {format_timestamp(t.get('start_time', 0))} — {t.get('topic', '')}"
                              for t in outline_data]
                    outline_text = '\n'.join(topics)

        except Exception as e:
            print(f"  Warning: failed to download {dtype}: {e}")

    # Build markdown file
    frontmatter = [
        '---',
        'source: plaud',
        f'recorded: {recorded_date}',
        f'recorded_time: "{recorded_time}"',
        f'title: "{data.get("file_name", filename)}"',
        f'duration: "{format_duration(duration_ms)}"',
        f'speakers: {len(speakers) if "speakers" in dir() else 1}',
        f'plaud_id: "{file_id}"',
        f'scene: {data.get("scene", "")}',
        '---',
    ]

    sections = ['\n'.join(frontmatter)]
    sections.append(f'\n# {data.get("file_name", filename)}')

    if summary_text:
        sections.append(f'\n## Summary\n\n{summary_text}')

    if outline_text:
        sections.append(f'\n## Outline\n\n{outline_text}')

    if transcript_text:
        sections.append(f'\n## Transcript\n{transcript_text}')

    transcript_path.write_text('\n'.join(sections), encoding='utf-8')

    # Download audio
    if download_audio:
        audio_path = file_dir / "audio.mp3"
        if not audio_path.exists() or force:
            try:
                client.download_audio(file_id, str(audio_path))
            except Exception as e:
                print(f"  Warning: failed to download audio: {e}")

    return True


def main():
    parser = argparse.ArgumentParser(description="Sync Plaud recordings to local folder")
    default_output = os.environ.get('PLAUD_DATA_DIR', os.path.expanduser('~/plaud-data'))
    parser.add_argument('--output', '-o',
                        default=default_output,
                        help=f'Output directory (default: {default_output})')
    parser.add_argument('--no-audio', action='store_true',
                        help='Skip audio file downloads')
    parser.add_argument('--force', action='store_true',
                        help='Re-download existing files')
    parser.add_argument('--delay', type=float, default=1.0,
                        help='Delay between API calls in seconds (default: 1.0)')
    args = parser.parse_args()

    token = os.environ.get('PLAUD_TOKEN')
    if not token:
        print("Error: PLAUD_TOKEN not set. Check .env file.")
        sys.exit(1)

    api_domain = os.environ.get('PLAUD_API_DOMAIN')
    client = PlaudClient(token, api_domain=api_domain)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Fetching file list...")
    files = client.list_files()
    print(f"Found {len(files)} files\n")

    new_count = 0
    skip_count = 0

    for i, f in enumerate(files, 1):
        name = f.get('filename', f['id'])
        duration = format_duration(f.get('duration', 0))

        print(f"[{i}/{len(files)}] {name} ({duration})")

        downloaded = sync_file(
            client, f, output_dir,
            download_audio=not args.no_audio,
            force=args.force
        )

        if downloaded:
            print(f"  ✓ downloaded")
            new_count += 1
            time.sleep(args.delay)
        else:
            print(f"  — skipped (exists)")
            skip_count += 1

    print(f"\nDone! {new_count} new, {skip_count} skipped. Output: {output_dir}")


if __name__ == '__main__':
    main()
