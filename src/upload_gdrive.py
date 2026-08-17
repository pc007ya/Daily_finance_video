from __future__ import annotations

import json
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        token_uri=TOKEN_URI,
        client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _find_existing(service, folder_id: str, name: str):
    safe = name.replace("'", "\\'")
    q = f"name = '{safe}' and '{folder_id}' in parents and trashed = false"
    res = service.files().list(
        q=q,
        spaces="drive",
        fields="files(id,name,webViewLink)",
        pageSize=10,
    ).execute()
    files = res.get("files", [])
    return files[0] if files else None


def upload_mp4(mp4_path: str | Path, folder_id: str | None = None) -> dict:
    path = Path(mp4_path)
    if not path.exists():
        raise FileNotFoundError(path)

    folder_id = folder_id or os.environ["GDRIVE_FOLDER_ID"]
    service = _service()

    existing = _find_existing(service, folder_id, path.name)
    media = MediaFileUpload(str(path), mimetype="video/mp4", resumable=True)

    if existing:
        uploaded = service.files().update(
            fileId=existing["id"],
            media_body=media,
            fields="id,name,webViewLink,webContentLink,size,modifiedTime",
        ).execute()
        action = "updated"
    else:
        uploaded = service.files().create(
            body={"name": path.name, "parents": [folder_id]},
            media_body=media,
            fields="id,name,webViewLink,webContentLink,size,modifiedTime",
        ).execute()
        action = "created"

    uploaded["action"] = action
    return uploaded


def main():
    output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
    candidates = sorted(
        output_dir.rglob("daily_finance_*.mp4"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise RuntimeError(f"No daily_finance_*.mp4 found under {output_dir}")

    result = upload_mp4(candidates[0])
    result_path = output_dir / "gdrive_upload.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
