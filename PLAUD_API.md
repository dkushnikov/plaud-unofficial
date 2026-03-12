# Plaud API Reverse Engineering Documentation

## Overview

This document describes the Plaud API endpoints discovered through reverse engineering the web application at https://web.plaud.ai/

## Authentication

### JWT Token
- **Storage**: `localStorage.tokenstr`
- **Format**: `bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
- **Header**: `Authorization: bearer <token>`

### Token Claims (decoded)
```json
{
  "sub": "<user_id>",
  "aud": "",
  "exp": <expiration_timestamp>,
  "iat": <issued_at_timestamp>,
  "client_id": "web",
  "region": "aws:eu-central-1"
}
```

## API Base URL

The API domain is region-specific and stored in localStorage:
- **EU Central 1**: `https://api-euc1.plaud.ai`
- **Global/Default**: `https://api.plaud.ai` (observed in XHR logs — may be used for migrated accounts or as a fallback)
- **Storage key**: `plaud_user_api_domain`

**Note**: Some accounts use `api.plaud.ai` instead of the region-specific domain. The web app's XHR requests have been observed going to `api.plaud.ai`. If the region-specific domain doesn't work, try the global one.

## Endpoints

### Common Request Headers

Beyond `Authorization` and `Content-Type`, the web app sends additional headers:

| Header | Example Value | Notes |
|--------|---------------|-------|
| `app-language` | `en` | UI language |
| `app-platform` | `web` | Client platform |
| `edit-from` | `web` | Edit origin |
| `timezone` | `Europe/Madrid` | User's timezone (IANA format) |
| `x-device-id` | `e6bb5eac367f69a6` | Device identifier (16-char hex) |
| `x-pld-tag` | `e6bb5eac367f69a6` | Same as x-device-id |
| `x-pld-user` | `140b9889eff6...` | User hash (64-char hex, SHA-256-like) |

Most endpoints work with just `Authorization`. The extra headers may be required for transcription triggers.

### File Operations

#### List All Files
```
GET /file/simple/web
Authorization: bearer <token>
```

**Response:**
```json
{
  "status": 0,
  "msg": "success",
  "data_file_total": 8,
  "data_file_list": [
    {
      "id": "af9e46896091e31b29775331960e66f9",
      "filename": "Recording Title",
      "duration": 989000,
      "is_trash": false,
      "start_time": 1737538282000,
      "scene": 102,
      "is_trans": true,
      "is_summary": true,
      "filetag_id_list": ["folder_id"],
      ...
    }
  ]
}
```

#### Get File Details
```
GET /file/detail/{file_id}
Authorization: bearer <token>
```

**Response:**
```json
{
  "data": {
    "file_id": "af9e46896091e31b29775331960e66f9",
    "file_name": "Recording Title",
    "file_version": "...",
    "duration": 989000,
    "is_trash": false,
    "start_time": "2026-01-22T09:31:22",
    "scene": 102,
    "serial_number": "...",
    "session_id": "...",
    "filetag_id_list": [],
    "content_list": [...],
    "trans_result": {...},
    "ai_content": {...}
  }
}
```

#### Download Audio File (Direct MP3)
```
GET /file/download/{file_id}
Authorization: bearer <token>
```

**Response**: Binary MP3 data (ID3 tagged)

#### Batch File Details
```
POST /file/list
Authorization: bearer <token>
Content-Type: application/json

Body: ["file_id_1", "file_id_2", ...]
```

### File Tags

#### Get File Tags/Folders
```
GET /filetag/
Authorization: bearer <token>
```

### AI Features

#### Get AI Task Status
```
GET /ai/file-task-status?file_ids={file_id}
Authorization: bearer <token>
```

#### Update File Config (Pre-Transcription)
```
PATCH /file/{file_id}
Authorization: bearer <token>
Content-Type: application/json

Body:
{
  "extra_data": {
    "tranConfig": {
      "language": "auto",
      "type_type": "system",
      "type": "AI-CHOICE",
      "diarization": 1,
      "llm": "claude-sonnet-4.6"
    }
  }
}
```

**Notes:**
- Must be called before triggering transcription to save config
- `language`: `"auto"` for auto-detect, or ISO code like `"en"`, `"ru"`, `"es"`
- `type` / `type_type`: summary template. `"AI-CHOICE"` + `"system"` = Adaptive Summary. Other observed values: custom template types
- `diarization`: `1` = enabled, `0` = disabled
- `llm`: AI model for summary. Known values: `"claude-sonnet-4.6"`, likely others available

#### Trigger Transcription + AI Summary
```
POST /ai/transsumm/{file_id}
Authorization: bearer <token>
Content-Type: application/json

Body:
{
  "is_reload": 0,
  "summ_type": "AI-CHOICE",
  "summ_type_type": "system",
  "info": "{\"language\":\"auto\",\"diarization\":1,\"llm\":\"claude-sonnet-4.6\",\"timezone\":1}",
  "support_mul_summ": true
}
```

**Notes:**
- This is the endpoint that actually starts transcription and AI processing
- `is_reload`: `0` for first transcription, likely `1` for re-transcription
- `info` is a **JSON string** (not an object) containing transcription parameters
- `timezone`: numeric offset (e.g., `1` for UTC+1). Different from the `timezone` header which uses IANA format
- `support_mul_summ`: whether to support multiple summary types
- Two-step flow: PATCH config first, then POST transsumm

#### Get Transcription Status
```
GET /ai/trans-status
Authorization: bearer <token>
```

**Response:** Returns current transcription queue/processing status.

#### Get Transcription Quota
```
GET /user/stat/transcription/quota?notification=tag
Authorization: bearer <token>
```

**Response:** Returns remaining transcription minutes/credits for the account.

#### Query Notes
```
GET /ai/query_note?file_id={file_id}
Authorization: bearer <token>
```

#### Get Recommended Questions
```
POST /ask/recommend_questions
Authorization: bearer <token>
Content-Type: application/json

Body: {"file_id": "..."}
```

### Languages

#### List Supported Languages
```
GET /others/language_list
Authorization: bearer <token>
```

**Response:**
```json
{
  "status": 0,
  "msg": "success",
  "data": {
    "default_language_list": {
      "auto": {"ori_content": "Auto Detect", "translate_content": "Auto Detect"},
      "en": {"ori_content": "English(US)", "translate_content": "English(US)"},
      "en-1": {"ori_content": "English(UK)", "translate_content": "English(UK)"},
      "ru": {"ori_content": "Русский", "translate_content": "Russian"},
      ...
    }
  }
}
```

**Notes:**
- Returns 113 supported languages
- Keys are language codes, values contain `ori_content` (native name) and `translate_content` (English name)
- See Language Codes Reference below for key codes

#### Get Recently Used Languages
```
GET /ai/recently_used_language
Authorization: bearer <token>
```

**Response:**
```json
{
  "status": 0,
  "msg": "success",
  "data": {
    "default_recently_used_language": ["auto", "en", "ru"]
  }
}
```

### Templates

#### Get Recently Used Templates
```
POST /summary/community/templates/recently_used
Authorization: bearer <token>
Content-Type: application/json

Body: {"language_os": "en", "scene": 1}
```

**Response:**
```json
{
  "status": 0,
  "msg": "success",
  "data": [
    {
      "type": "official",
      "template": {
        "id": "AI-CHOICE",
        "name": "Adaptive Summary",
        ...
      }
    },
    {
      "type": "community",
      "template": {
        "id": "...",
        "name": "...",
        ...
      }
    }
  ]
}
```

**Notes:**
- `scene` parameter filters templates by applicable scene type
- Returns both official and community templates

#### Get Template Categories
```
GET /summary/community/templates/categorys?language_os=en
Authorization: bearer <token>
```

**Response:**
```json
{
  "status": 0,
  "msg": "success",
  "data": [
    {"id": "cat_general", "name": "General"},
    {"id": "cat_meeting", "name": "Meeting"},
    ...
  ]
}
```

### User & Config

#### Get User Profile
```
GET /user/me
Authorization: bearer <token>
```

**Response:**
```json
{
  "status": 0,
  "msg": "success",
  "data": {
    "user_id": "...",
    "email": "...",
    "membership_type": "pro",
    "membership_flag": 1,
    "seconds_left": 360000,
    "seconds_total": 360000,
    "region": "aws:eu-central-1",
    ...
  }
}
```

**Key fields:**
- `membership_type`: Subscription plan (e.g., `"pro"`, `"free"`)
- `membership_flag`: Active membership indicator
- `seconds_left`: Remaining transcription seconds in current period
- `seconds_total`: Total transcription seconds in current period
- `region`: User's API region

#### Get User Settings
```
GET /user/me/settings
Authorization: bearer <token>
```

**Response:**
```json
{
  "status": 0,
  "msg": "success",
  "data": {
    "industry": "technology",
    "words": ["Manychat", "custom term"],
    "language": "en",
    "auto_speaker_tagging": true,
    "speaker_cloud_enabled": true,
    ...
  }
}
```

**Key fields:**
- `industry`: User's industry setting (affects AI summaries)
- `words`: Custom vocabulary list (proper nouns, jargon the AI should recognize)
- `language`: Default UI/transcription language
- `auto_speaker_tagging`: Whether automatic speaker identification is enabled
- `speaker_cloud_enabled`: Whether cloud-based speaker recognition is enabled

#### Get App Config
```
GET /config/init?platform=web&version=1.1.1
Authorization: bearer <token>
```

**Response:** Returns app configuration including `speaker_embedding_config`, `region`, `use_thought_partner`, websocket settings.

### Sharing

#### Get Private Share Info
```
POST /share/private/get
Authorization: bearer <token>
Content-Type: application/json

Body: {"file_id": "..."}
```

#### Get Public Share Info
```
POST /share/public/get
Authorization: bearer <token>
Content-Type: application/json

Body: {"file_id": "..."}
```

## S3 Storage URLs

### Audio Files (Pre-signed URLs)
```
https://euc1-prod-plaud-bucket.s3.amazonaws.com/audiofiles/{file_id}.mp3
```

Query parameters for AWS signature:
- `X-Amz-Algorithm`
- `X-Amz-Credential`
- `X-Amz-Date`
- `X-Amz-Expires`
- `X-Amz-SignedHeaders`
- `X-Amz-Signature`

### Transcript Storage
```
https://euc1-prod-plaud-content-storage.s3.amazonaws.com/permanent/{user_id}/file_transcript/{file_id}/trans_result.json.gz
```

### General Content Storage
```
https://euc1-prod-plaud-content-storage.s3.amazonaws.com/permanent/{user_id}/general/{content_id}
```

## File ID Format

- **Length**: 32 characters
- **Format**: Hexadecimal string (MD5-like hash)
- **Example**: `af9e46896091e31b29775331960e66f9`

## Scene Types

| Scene Code | Description |
|------------|-------------|
| 0 | All/Default |
| 1 | Desktop/Import |
| 2 | Discussion/Seminar |
| 102 | Note Mode Recording |
| 103 | Note Mode (variant) |
| 1000 | Media Import |

## Getting File IDs

File IDs can be obtained from:
1. The URL when viewing a file: `https://web.plaud.ai/file/{file_id}`
2. The Vue store `fileManage.recentlyUpdatedList`
3. Browser DevTools Network tab

## Rate Limiting

No specific rate limits observed, but standard API best practices recommended.

## Official Templates Reference

| Template ID | Name | Available in Scenes |
|-------------|------|---------------------|
| `AI-CHOICE` | Adaptive Summary | all |
| `REASONING-NOTE` | Reasoning Summary | all |
| `MEETING` | Meeting Note | 0, 1, 102, 103, 1000 |
| `MEETING-SEMINAR` | Discussion Summary | 0, 2 |

Use the template ID as the `--template` flag value in the `transcribe` command (e.g., `--template MEETING`).

## Template Categories Reference

15 categories for browsing community templates:

| Category ID | Description |
|-------------|-------------|
| `cat_general` | General |
| `cat_meeting` | Meeting |
| `cat_speech` | Speech |
| `cat_call` | Call |
| `cat_interview` | Interview |
| `cat_medical` | Medical |
| `cat_sales` | Sales |
| `cat_consulting` | Consulting |
| `cat_education` | Education |
| `cat_construction` | Construction |
| `cat_it_engineering` | IT/Engineering |
| `cat_legal` | Legal |
| `cat_real_estate` | Real Estate |
| `cat_financial` | Financial |
| `cat_functional` | Functional |

## Language Codes Reference

113 languages supported. Key codes:

| Code | Language |
|------|----------|
| `auto` | Auto Detect |
| `en` | English (US) |
| `en-1` | English (UK) |
| `en-2` | English (AU) |
| `en-3` through `en-8` | Other English variants |
| `ru` | Russian |
| `zh-0` | Chinese Simplified (Mandarin) |
| `zh-1` | Chinese Traditional (Mandarin) |
| `zh-hk-0` | Chinese Simplified (Cantonese) |
| `zh-hk-1` | Chinese Traditional (Cantonese) |
| `fr` | French (France) |
| `fr-1` | French (Canada) |
| `es` | Spanish (Spain) |
| `es-1` | Spanish (US) |
| `es-2` | Spanish (Latin America) |

Use `python3 plaud_client.py languages` for the full list, or `--json` for machine-readable output.

## User Profile Fields Reference

Fields returned by `GET /user/me`:

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | string | Unique user identifier |
| `email` | string | Account email |
| `membership_type` | string | Plan name (e.g., `"pro"`, `"free"`) |
| `membership_flag` | int | Active membership indicator (1 = active) |
| `seconds_left` | int | Remaining transcription seconds |
| `seconds_total` | int | Total transcription seconds in period |
| `region` | string | API region (e.g., `"aws:eu-central-1"`) |

## Notes

- Token expiration is long-lived (appears to be ~10 months)
- The API uses standard REST conventions
- All timestamps are in ISO 8601 format
- File durations are in milliseconds
