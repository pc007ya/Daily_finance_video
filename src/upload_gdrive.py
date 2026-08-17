from __future__ import annotations

import json
import os
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _service():
    raw = os.environ["GDRIVE_SERVICE_ACCOUNT_JSON"]
    info = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _find_existing(service, folder_id: str, name: str):
    safe = name.replace("'", "\\'")
    q = f"name = '{safe}' and '{folder_id}' in parents and trashed = false"
    res = service.files().list(q=q, spaces="drive", fields="files(id,name,webViewLink)", pageSize=10).execute()
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
        file_id = existing["id"]
        uploaded = service.files().update(
            fileId=file_id,
            media_body=media,
            fields="id,name,webViewLink,webContentLink,size,modifiedTime",
        ).execute()
        action = "updated"
    else:
        metadata = {"name": path.name, "parents": [folder_id]}
        uploaded = service.files().create(
            body=metadata,
            media_body=media,
            fields="id,name,webViewLink,webContentLink,size,modifiedTime",
        ).execute()
        action = "created"

    uploaded["action"] = action
    return uploaded


def main():
    output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
    candidates = sorted(output_dir.rglob("daily_finance_*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError(f"No daily_finance_*.mp4 found under {output_dir}")

    result = upload_mp4(candidates[0])
    result_path = output_dir / "gdrive_upload.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
