from playwright.sync_api import sync_playwright
import json
import re
import argparse
from pathlib import Path


class TwitterReplyScraper:

    def __init__(self, auth_token, profile_dir="twitter_profile"):
        self.auth_token = auth_token
        self.profile_dir = profile_dir
        self.replies = []


    def scrape_replies(self, tweet_url, limit=200):

        tweet_id = tweet_url.split("/")[-1]

        collected = 0
        seen_ids = set()

        while collected < limit:

            try:

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

                    print("[INFO] Opening tweet")

                    page.goto(tweet_url, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)

                    scroll_count = 0
                    max_scroll = 1000

                    last_height = 0
                    no_new_scroll = 0

                    while collected < limit and scroll_count < max_scroll:

                        articles = page.query_selector_all('article[role="article"]')

                        for article in articles:

                            if collected >= limit:
                                break

                            try:

                                link_elem = article.query_selector('a[href*="/status/"]')

                                if not link_elem:
                                    continue

                                href = link_elem.get_attribute("href")

                                reply_id = href.split("/")[-1]

                                if reply_id == tweet_id:
                                    continue

                                if reply_id in seen_ids:
                                    continue

                                seen_ids.add(reply_id)

                                text_elem = article.query_selector('[data-testid="tweetText"]')
                                text = text_elem.inner_text() if text_elem else ""

                                username_elem = article.query_selector('[data-testid="User-Name"] a')

                                username = "unknown"

                                if username_elem:
                                    profile = username_elem.get_attribute("href")
                                    username = profile.split("/")[-1]

                                time_elem = article.query_selector("time")
                                timestamp = time_elem.get_attribute("datetime") if time_elem else ""

                                hashtags = re.findall(r"#(\w+)", text)
                                mentions = re.findall(r"@(\w+)", text)

                                reply = {
                                    "reply_id": reply_id,
                                    "username": username,
                                    "text": text,
                                    "timestamp": timestamp,
                                    "hashtags": hashtags,
                                    "mentions": mentions,
                                    "reply_to": tweet_id
                                }

                                self.replies.append(reply)

                                collected += 1

                                print(f"[+] {collected}/{limit} @{username}")

                            except:
                                pass


                        new_height = page.evaluate("document.body.scrollHeight")

                        if new_height == last_height:
                            no_new_scroll += 1
                        else:
                            no_new_scroll = 0

                        last_height = new_height


                        if no_new_scroll >= 4:

                            print("[INFO] forcing load")

                            page.evaluate("window.scrollBy(0,-1000)")
                            page.wait_for_timeout(300)

                            page.evaluate("window.scrollBy(0,2000)")
                            page.wait_for_timeout(300)

                            no_new_scroll = 0

                        else:

                            page.evaluate("window.scrollBy(0,1500)")
                            page.wait_for_timeout(350)


                        scroll_count += 1


                    context.close()

                    break


            except Exception as e:

                print("[RECOVERY] Browser crashed, restarting...")
                print(e)

        return self.replies


    def save_json(self, filename):

        if not self.replies:
            print("No replies collected")
            return

        output = Path.cwd() / filename

        with open(output, "w", encoding="utf-8") as f:
            json.dump(self.replies, f, ensure_ascii=False, indent=2)

        print("\nSaved", len(self.replies), "replies")
        print("File:", output)



if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("--url", required=True)
    parser.add_argument("--limit", type=int, default=200)

    args = parser.parse_args()

    AUTH_TOKEN = " "

    scraper = TwitterReplyScraper(AUTH_TOKEN)

    try:

        replies = scraper.scrape_replies(args.url, args.limit)

    except KeyboardInterrupt:

        print("\n[STOP] Scraping interrupted by user.")

    finally:

        scraper.save_json("tweet_replies.json")
        
