#!/usr/bin/env python3
"""
엑셀(CSV)로 준비한 크리에이터 목록을 Supabase creators + youtube_channels 에 한 번에 등록합니다.
사용법: CSV 파일 경로를 인자로 주고, .env 또는 환경변수에 SUPABASE_URL, SUPABASE_SERVICE_KEY 설정 후 실행.
  python automation/upload_creators_and_channels.py docs/내가_채운_크리에이터목록.csv
"""
import csv
import os
import sys

# 프로젝트 루트의 .env 자동 로드 (python-dotenv 있으면)
try:
    from dotenv import load_dotenv
    # 실행 위치(프로젝트 루트) 또는 스크립트 기준 상위 폴더에서 .env 찾기
    for path in [".env", os.path.join(os.path.dirname(__file__), "..", ".env")]:
        if os.path.isfile(path):
            load_dotenv(os.path.abspath(path))
            break
    else:
        load_dotenv()  # cwd 기준
except ImportError:
    pass

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# creators 테이블 컬럼명 (Supabase Table Editor에서 실제 컬럼명 확인 후 필요 시 수정)
CREATORS_COLUMNS = ["name", "subscribers", "sub_count_date", "link_url"]
# 만약 실제 테이블이 creator_name, updated_at 등을 쓰면 예:
# CREATORS_COLUMNS = ["creator_name", "subscribers", "updated_at", "link_url"]


def main():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("환경변수 SUPABASE_URL, SUPABASE_SERVICE_KEY 를 설정해 주세요.")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("사용법: python automation/upload_creators_and_channels.py <CSV파일경로>")
        print("예: python automation/upload_creators_and_channels.py docs/내가_채운_크리에이터목록.csv")
        sys.exit(1)

    csv_path = sys.argv[1]
    if not os.path.isfile(csv_path):
        print(f"파일을 찾을 수 없습니다: {csv_path}")
        sys.exit(1)

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "youtube_channel_id" not in reader.fieldnames:
            print("CSV에 name, subscribers, sub_count_date, link_url, youtube_channel_id 컬럼이 있어야 합니다.")
            sys.exit(1)

        for i, row in enumerate(reader, start=1):
            name = (row.get("name") or "").strip()
            youtube_channel_id = (row.get("youtube_channel_id") or "").strip()
            if not name or not youtube_channel_id:
                print(f"[{i}행] name 또는 youtube_channel_id 비어 있음, 건너뜀: {name!r} / {youtube_channel_id!r}")
                continue
            if not youtube_channel_id.startswith("UC"):
                print(f"[{i}행] youtube_channel_id 는 UC 로 시작해야 합니다: {youtube_channel_id!r}")
                continue

            # creators 에 넣을 payload (컬럼명만 사용)
            creator_payload = {}
            for col in CREATORS_COLUMNS:
                val = (row.get(col) or "").strip()
                if col == "subscribers":
                    # "1,710,000" 같은 쉼표 제거 후 숫자로
                    num_str = val.replace(",", "")
                    if num_str.isdigit():
                        val = int(num_str)
                creator_payload[col] = val if val else None

            # 1) creators INSERT
            r = requests.post(
                f"{SUPABASE_URL}/rest/v1/creators",
                headers=headers,
                json=creator_payload,
            )
            if r.status_code not in (200, 201):
                print(f"[{i}행] creators INSERT 실패: {r.status_code} {r.text}")
                continue

            created = r.json()
            if isinstance(created, list) and len(created) > 0:
                creator_id = created[0].get("id")
            elif isinstance(created, dict):
                creator_id = created.get("id")
            else:
                print(f"[{i}행] creators 응답에서 id를 찾을 수 없음: {created}")
                continue

            # 2) youtube_channels INSERT
            r2 = requests.post(
                f"{SUPABASE_URL}/rest/v1/youtube_channels",
                headers=headers,
                json={"creator_id": creator_id, "youtube_channel_id": youtube_channel_id},
            )
            if r2.status_code not in (200, 201):
                print(f"[{i}행] youtube_channels INSERT 실패: {r2.status_code} {r2.text}")
                continue

            print(f"[{i}행] OK: {name} (creator_id={creator_id}, channel={youtube_channel_id})")

    print("완료.")


if __name__ == "__main__":
    main()
