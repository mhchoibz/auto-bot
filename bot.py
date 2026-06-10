import os
import time
import requests
import anthropic

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
THREADS_BASE_URL = "https://graph.threads.net/v1.0"
POSTS_PER_RUN = 3

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
THREADS_USER_ID = os.environ["THREADS_USER_ID"]
THREADS_ACCESS_TOKEN = os.environ["THREADS_ACCESS_TOKEN"]


def get_hackernews_top(limit=POSTS_PER_RUN):
    story_ids = requests.get(HN_TOP_URL, timeout=10).json()[: limit * 5]

    articles = []
    for story_id in story_ids:
        item = requests.get(HN_ITEM_URL.format(story_id), timeout=10).json()
        if item.get("url") and item.get("title"):
            articles.append(
                {
                    "title": item["title"],
                    "url": item["url"],
                    "score": item.get("score", 0),
                    "comments": item.get("descendants", 0),
                }
            )
        if len(articles) >= limit:
            break

    return articles


def claude_summarize(article):
    prompt = f"""다음 IT/기술 뉴스를 한국어 Threads 포스트로 작성해줘.

제목: {article['title']}
URL: {article['url']}
점수: {article['score']} | 댓글: {article['comments']}

요구사항:
- 500자 이내
- 핵심 내용을 쉽게 설명
- 왜 중요한지 한 문장으로
- 관련 해시태그 3~5개 포함
- URL은 맨 마지막에
- 딱딱하지 않고 자연스러운 톤"""

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def post_to_threads(post_text):
    # Step 1: 미디어 컨테이너 생성
    container_resp = requests.post(
        f"{THREADS_BASE_URL}/{THREADS_USER_ID}/threads",
        data={
            "media_type": "TEXT",
            "text": post_text,
            "access_token": THREADS_ACCESS_TOKEN,
        },
        timeout=10,
    )
    container_resp.raise_for_status()
    creation_id = container_resp.json()["id"]

    # Threads API는 생성 후 게시까지 약간의 대기 필요
    time.sleep(5)

    # Step 2: 게시
    publish_resp = requests.post(
        f"{THREADS_BASE_URL}/{THREADS_USER_ID}/threads_publish",
        data={
            "creation_id": creation_id,
            "access_token": THREADS_ACCESS_TOKEN,
        },
        timeout=10,
    )
    publish_resp.raise_for_status()
    return publish_resp.json()["id"]


def main():
    print("HackerNews 인기 글 가져오는 중...")
    articles = get_hackernews_top()
    print(f"{len(articles)}개 아티클 로드됨\n")

    for i, article in enumerate(articles, 1):
        print(f"[{i}/{len(articles)}] {article['title']}")
        try:
            post_text = claude_summarize(article)
            print(f"포스트 생성됨 ({len(post_text)}자)")

            thread_id = post_to_threads(post_text)
            print(f"Threads 게시 완료 → {thread_id}\n")
        except Exception as e:
            print(f"오류 발생, 스킵: {e}\n")

        time.sleep(2)


if __name__ == "__main__":
    main()
