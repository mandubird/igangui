import os
import requests
from bs4 import BeautifulSoup

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

# 크롤링할 크리에이터 & 강의 페이지 목록 (실제 UUID와 URL로 교체하세요)
TARGETS = [
    {
        "creator_id": "UUID-여기에-입력",
        "url": "https://class101.net/ko/channels/채널명",
    },
]


def crawl_and_insert(target):
    res = requests.get(target["url"], timeout=10)
    soup = BeautifulSoup(res.text, "html.parser")

    # 강의 제목 파싱 (사이트 구조에 따라 수정 필요)
    title_tag = soup.find("h1")
    if not title_tag:
        print(f"제목 파싱 실패: {target['url']}")
        return

    title = title_tag.text.strip()

    # Supabase courses 테이블에 INSERT
    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/courses",
        headers={
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json={
            "title": title,
            "creator_id": target["creator_id"],
            "source": "crawler",
        },
    )

    if response.status_code in (200, 201):
        print(f"등록 성공: {title}")
    else:
        print(f"등록 실패 ({response.status_code}): {response.text}")


for target in TARGETS:
    crawl_and_insert(target)
