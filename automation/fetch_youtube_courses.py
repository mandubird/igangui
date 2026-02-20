#!/usr/bin/env python3
"""
youtube_channels 테이블의 채널마다 YouTube API로 최신 영상을 가져와 courses 에 넣습니다.
Make.com 없이 로컬에서 한 번 실행해서 강의가 들어가는지 확인할 수 있습니다.

필요 환경변수: SUPABASE_URL, SUPABASE_SERVICE_KEY, YOUTUBE_API_KEY
실행: python automation/fetch_youtube_courses.py
"""
import os
import sys
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    for path in [".env", os.path.join(os.path.dirname(__file__), "..", ".env")]:
        if os.path.isfile(path):
            load_dotenv(os.path.abspath(path))
            break
    else:
        load_dotenv()
except ImportError:
    pass

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

# 제목에 이 중 하나라도 있으면 강의로 넣음. 빈 리스트 [] 로 바꾸면 모든 최신 영상을 넣음.
TITLE_KEYWORDS = ["강의", "클래스", "오픈"]


def get_channels():
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/youtube_channels?select=creator_id,youtube_channel_id",
        headers={
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
        },
    )
    r.raise_for_status()
    return r.json()


def youtube_search(channel_id: str, max_results: int = 10):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "key": YOUTUBE_API_KEY,
        "channelId": channel_id,
        "part": "snippet",
        "order": "date",
        "maxResults": max_results,
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def insert_course(creator_id: str, title: str):
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/courses",
        headers={
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json={
            "title": title,
            "creator_id": creator_id,
            "source": "youtube_script",
            "auto_detected_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return r.status_code in (200, 201), r.status_code, r.text


def main():
    if not all([SUPABASE_URL, SUPABASE_SERVICE_KEY, YOUTUBE_API_KEY]):
        print("환경변수 SUPABASE_URL, SUPABASE_SERVICE_KEY, YOUTUBE_API_KEY 를 설정해 주세요.")
        print(".env 에 YOUTUBE_API_KEY 도 추가했는지 확인하세요.")
        sys.exit(1)

    channels = get_channels()
    if not channels:
        print("youtube_channels 테이블에 행이 없습니다.")
        sys.exit(0)

    print(f"채널 {len(channels)}개 처리 시작...")
    inserted = 0
    skipped = 0
    errors = 0

    for row in channels:
        creator_id = row["creator_id"]
        channel_id = row["youtube_channel_id"]
        try:
            data = youtube_search(channel_id)
        except Exception as e:
            print(f"  [API 오류] {channel_id}: {e}")
            errors += 1
            continue

        items = data.get("items") or []
        for item in items:
            if item.get("id", {}).get("kind") != "youtube#video":
                continue
            snippet = item.get("snippet") or {}
            title = (snippet.get("title") or "").strip()
            if not title:
                continue
            if TITLE_KEYWORDS and not any(kw in title for kw in TITLE_KEYWORDS):
                skipped += 1
                continue
            ok, code, body = insert_course(creator_id, title)
            if ok:
                inserted += 1
                print(f"  + {title[:50]}...")
            else:
                if "23505" in body or "duplicate" in body.lower():
                    skipped += 1
                else:
                    errors += 1
                    print(f"  ! INSERT 실패 ({code}): {title[:40]}...")

    print(f"\n완료. 등록={inserted}, 건너뜀={skipped}, 오류={errors}")


if __name__ == "__main__":
    main()
