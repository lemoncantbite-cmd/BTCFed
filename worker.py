"""
RSS -> dedup (URL hash, title hash, embedding) -> sentiment -> Supabase.
Environment: SUPABASE_URL, SUPABASE_SERVICE_KEY
"""
import hashlib
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
from sentence_transformers import SentenceTransformer
from supabase import create_client
from transformers import pipeline

EMB_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
SENT_MODEL = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
THRESHOLD = 0.85
PER_FEED_LIMIT = 30
MAX_AGE_HOURS = 24      # isse purani news ingest nahi hogi
EMPTY_WARNED = set()
LOOP_SLEEP_SEC = 30     # --loop mode mein har round ke beech ka gap
UA = "Mozilla/5.0 (compatible; NewsFeedBot/1.0)"
TRACK = ("utm_", "fbclid", "gclid", "cmpid", "ocid")

# .env file (isi folder mein) se keys automatically padh leta hai
def load_env_file():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()
for needed in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
    if not os.environ.get(needed):
        sys.exit(f"{needed} nahi mila. C:\\BTCFed mein .env file banao (steps chat mein diye hain).")

supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
if supabase_url.endswith("/rest/v1"):
    supabase_url = supabase_url[: -len("/rest/v1")]
sb = create_client(supabase_url, os.environ["SUPABASE_SERVICE_KEY"])
emb = SentenceTransformer(EMB_MODEL)
sent = pipeline(
    "text-classification",
    model=SENT_MODEL,
    top_k=None,
    truncation=True,
    max_length=256,
)


def canon_url(url):
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query)
        if not key.lower().startswith(TRACK) and key.lower() not in ("ref", "ref_src", "source")
    ]
    path = re.sub(r"/amp/?$", "", parts.path).rstrip("/")
    host = parts.netloc.lower().removeprefix("www.").removeprefix("amp.")
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(query), ""))


def norm_title(title):
    title = html.unescape(title).lower()
    title = re.sub(r"\s[-|–—]\s[^-|–—]{2,30}$", "", title)
    title = re.sub(r"[^\w\s]", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def hash_text(value):
    return hashlib.sha1(value.encode()).hexdigest()


def clean(text, limit=300):
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def pub_time(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    return datetime(*parsed[:6], tzinfo=timezone.utc) if parsed else datetime.now(timezone.utc)


def vec_str(vector):
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


def sentiment(text):
    scores = {result["label"].lower(): result["score"] for result in sent(text)[0]}
    positive, negative = scores.get("positive", 0), scores.get("negative", 0)
    label = max(scores, key=scores.get)
    return round(positive - negative, 3), label


def known(column, hashes):
    """Return {hash: story_id} for hashes already recorded in the database."""
    if not hashes:
        return {}
    response = (
        sb.table("story_sources")
        .select(f"{column},story_id")
        .in_(column, list(hashes))
        .execute()
    )
    return {row[column]: row["story_id"] for row in response.data}


def process_feed(source):
    feed = feedparser.parse(source["url"], agent=UA)
    entries = feed.entries[:PER_FEED_LIMIT]
    rows = []
    if not entries and source["name"] not in EMPTY_WARNED:
        EMPTY_WARNED.add(source["name"])
        print(
            f'{source["name"]}: 0 entries mili (status={feed.get("status")}). '
            "URL band/blocked ho sakta hai.",
            flush=True,
        )

    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    for entry in entries:
        if not entry.get("link") or not entry.get("title"):
            continue
        published = pub_time(entry)
        if published < cutoff:
            continue  # purani news skip
        rows.append(
            {
                "title": clean(entry["title"], 300),
                "summary": clean(entry.get("summary", "")),
                "url": canon_url(entry["link"]),
                "published_at": published,
            }
        )

    for row in rows:
        row["url_hash"] = hash_text(row["url"])
        row["title_hash"] = hash_text(norm_title(row["title"]))

    by_url = known("url_hash", {row["url_hash"] for row in rows})
    by_title = known("title_hash", {row["title_hash"] for row in rows})
    new_stories = duplicates_added = 0

    for row in rows:
        if row["url_hash"] in by_url:
            continue

        story_id = by_title.get(row["title_hash"])
        vector = None
        if not story_id:
            vector = emb.encode(row["title"])
            match = sb.rpc(
                "match_story",
                {"q": vec_str(vector), "threshold": THRESHOLD},
            ).execute()
            story_id = match.data or None

        if story_id:
            duplicates_added += 1
        else:
            score, label = sentiment(f'{row["title"]}. {row["summary"]}')
            inserted = (
                sb.table("stories")
                .insert(
                    {
                        "title": row["title"],
                        "summary": row["summary"],
                        "type": source["type"],
                        "country": source["country"],
                        "lang": source["lang"],
                        "published_at": row["published_at"].isoformat(),
                        "embedding": vec_str(vector),
                        "sentiment_score": score,
                        "sentiment_label": label,
                        "sentiment_model": SENT_MODEL,
                    }
                )
                .execute()
            )
            story_id = inserted.data[0]["id"]
            new_stories += 1

        sb.table("story_sources").upsert(
            {
                "story_id": story_id,
                "source": source["name"],
                "url": row["url"],
                "url_hash": row["url_hash"],
                "title_hash": row["title_hash"],
                "published_at": row["published_at"].isoformat(),
            },
            on_conflict="url_hash",
            ignore_duplicates=True,
        ).execute()

    if new_stories or duplicates_added:
        print(
            f'{source["name"]}: {new_stories} nayi story, '
            f"{duplicates_added} duplicate jude",
            flush=True,
        )


def run_once(sources):
    errors = []
    for source in sources:
        try:
            process_feed(source)
        except Exception as error:
            message = f'{source["name"]} FAIL: {error}'
            errors.append(message)
            print(message, file=sys.stderr, flush=True)
        time.sleep(0.3)
    return errors


if __name__ == "__main__":
    with open("sources.json", encoding="utf-8") as sources_file:
        sources = json.load(sources_file)

    if "--loop" in sys.argv:
        print("LIVE mode shuru. Band karne ke liye Ctrl+C dabao.", flush=True)
        while True:
            errs = run_once(sources)
            stamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{stamp}] round complete ({len(errs)} fail)", flush=True)
            time.sleep(LOOP_SLEEP_SEC)
    else:
        errors = run_once(sources)
        if errors:
            sys.exit(f"{len(errors)} feed(s) failed; see errors above.")