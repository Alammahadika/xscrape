from playwright.sync_api import sync_playwright
import re
import json
import argparse
from pathlib import Path
from urllib.parse import quote
from datetime import datetime


class TwitterScraper:

    def __init__(self, auth_token, output_file, profile_dir="twitter_profile"):
        self.auth_token = auth_token
        self.profile_dir = profile_dir
        self.output_file = output_file
        self.tweets = []


    def save_json(self):

        if not self.tweets:
            return

        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(self.tweets, f, ensure_ascii=False, indent=2)

        print(f"[SAVE] {len(self.tweets)} tweets → {self.output_file}")


    def wait_for_tweets(self, page, retries=6):

        for i in range(retries):

            articles = page.query_selector_all('article[role="article"]')

            if len(articles) > 0:
                return True

            print(f"[WAIT] tweets not loaded ({i+1}/{retries})")

            page.evaluate("window.scrollBy(0, window.innerHeight)")
            page.wait_for_timeout(1500)

        return False


    def scrape(self, query, limit=50):

        with sync_playwright() as p:

            print("[INFO] Launching browser")

            context = p.chromium.launch_persistent_context(
                user_data_dir=self.profile_dir,
                headless=False,
                viewport={"width":1280,"height":900}
            )

            page = context.pages[0] if context.pages else context.new_page()

            context.add_cookies([{
                "name": "auth_token",
                "value": self.auth_token,
                "domain": ".x.com",
                "path": "/",
                "secure": True,
                "httpOnly": True
            }])

            print("[INFO] Opening homepage")
            page.goto("https://x.com/home", wait_until="domcontentloaded")

            page.wait_for_timeout(3000)

            encoded_query = quote(query)

            search_url = f"https://x.com/search?q={encoded_query}&src=typed_query&f=live"

            print("[INFO] Opening search:", search_url)

            page.goto(search_url, wait_until="domcontentloaded")

            if not self.wait_for_tweets(page):
                print("[ERROR] Tweets never loaded")
                context.close()
                return []

            collected = 0
            seen_ids = set()

            scroll_count = 0
            max_scroll = 400

            last_height = 0
            no_new_scroll = 0

            while collected < limit and scroll_count < max_scroll:

                articles = page.query_selector_all('article[role="article"]')

                print(f"[VISIBLE] {len(articles)} tweets")

                for article in articles:

                    if collected >= limit:
                        break

                    try:

                        link_elem = article.query_selector('a[href*="/status/"]')

                        if not link_elem:
                            continue

                        href = link_elem.get_attribute("href")

                        tweet_id = href.split("/")[-1]

                        if tweet_id in seen_ids:
                            continue

                        seen_ids.add(tweet_id)

                        tweet_url = f"https://x.com{href}"

                        text_elem = article.query_selector('[data-testid="tweetText"]')
                        text = text_elem.inner_text() if text_elem else ""

                        username_elem = article.query_selector('[data-testid="User-Name"] a')
                        username = "unknown"

                        if username_elem:
                            profile = username_elem.get_attribute("href")
                            username = profile.split("/")[-1]

                        time_elem = article.query_selector("time")
                        timestamp = ""

                        if time_elem:
                            raw_time = time_elem.get_attribute("datetime")

                            try:
                                dt = datetime.fromisoformat(raw_time.replace("Z",""))
                                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                            except:
                                timestamp = raw_time

                        hashtags = re.findall(r"#(\w+)", text)
                        mentions = re.findall(r"@(\w+)", text)

                        tweet = {
                            "tweet_id": tweet_id,
                            "url": tweet_url,
                            "username": username,
                            "text": text,
                            "timestamp": timestamp,
                            "hashtags": hashtags,
                            "mentions": mentions,
                            "source_tag": query
                        }

                        self.tweets.append(tweet)

                        collected += 1

                        print(f"[+] {collected}/{limit} @{username}")

                        if collected % 50 == 0:
                            self.save_json()

                    except Exception as e:
                        print("[PARSE ERROR]", e)

                page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                page.wait_for_timeout(700)

                scroll_count += 1

            context.close()

            return self.tweets


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("--query", nargs="+", required=True)
    parser.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()

    query_text = " ".join(args.query)

    AUTH_TOKEN = " "

    safe_name = re.sub(r"\W+", "_", query_text)
    filename = safe_name + "_tweets.json"

    scraper = TwitterScraper(AUTH_TOKEN, filename)

    try:

        scraper.scrape(query_text, args.limit)

    except KeyboardInterrupt:

        print("\n[INTERRUPT] CTRL+C detected")

    finally:

        scraper.save_json()
