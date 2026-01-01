import argparse
import datetime
import random
import time
import requests
import os
import json
from pytrends.request import TrendReq
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import utils
import seo_utils

class AutoBlogger:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.logger = utils.logger
        self.history = utils.load_history()
        self.creds = self._authenticate_google()
        
        # API Keys
        self.news_api_key = utils.get_env('NEWSAPI_KEY')
        self.unsplash_key = utils.get_env('UNSPLASH_KEY')
        self.hf_token = utils.get_env('HF_TOKEN')
        self.hashnode_pat = utils.get_env('HASHNODE_PAT')
        self.devto_key = utils.get_env('DEVTO_API_KEY')
        self.blog_id = utils.get_env('BLOG_ID')

    def _authenticate_google(self):
        SCOPES = ['https://www.googleapis.com/auth/youtube.readonly', 'https://www.googleapis.com/auth/blogger']
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    self.logger.error(f"Google Auth failed: {e}")
                    return None
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        return creds

    def get_trending_topic(self):
        self.logger.info("Fetching trending topics...")
        try:
            pytrends = TrendReq(hl='en-US', tz=360)
            trending_searches = pytrends.trending_searches(pn='united_states')
            topics = trending_searches[0].tolist()
            
            # Filter duplicates
            for topic in topics[:10]: # Check top 10
                if not utils.is_duplicate_topic(topic, self.history):
                    self.logger.info(f"Selected Trend: {topic}")
                    return topic
            
            self.logger.warning("All top trends recently covered. Picking random one.")
            return random.choice(topics[:5])
        except Exception as e:
            self.logger.error(f"Trend fetch failed: {e}")
            return "Technology Trends 2026" # Fallback

    def fetch_news(self, topic):
        self.logger.info(f"Fetching news for {topic}...")
        from_date = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
        url = f"https://newsapi.org/v2/everything?q={topic}&from={from_date}&sortBy=relevancy&apiKey={self.news_api_key}"
        try:
            resp = requests.get(url)
            data = resp.json()
            articles = data.get('articles', [])[:10]
            return [f"{a['title']}: {a['description']}" for a in articles if a['description']]
        except Exception as e:
            self.logger.error(f"NewsAPI failed: {e}")
            return []

    def fetch_images(self, topic):
        self.logger.info(f"Fetching images for {topic}...")
        url = f"https://api.unsplash.com/search/photos?query={topic}&per_page=3&client_id={self.unsplash_key}"
        try:
            resp = requests.get(url)
            return resp.json().get('results', [])
        except Exception as e:
            self.logger.error(f"Unsplash failed: {e}")
            return []

    def fetch_video(self, topic):
        if not self.creds: return None
        self.logger.info(f"Fetching video for {topic}...")
        try:
            youtube = build('youtube', 'v3', credentials=self.creds)
            search = youtube.search().list(q=topic, part='snippet', maxResults=1, type='video').execute()
            items = search.get('items', [])
            if items:
                return items[0]
        except Exception as e:
            "intro": f"Write a catchy, human-like introduction for a blog post about {topic}. Start with a hook or question. Context: {context[:1000]}",
            "body": f"Explain the key details and why this matters for {topic}. Use simple language. Context: {context[:1000]}",
            "impact": f"What are the future consequences of {topic}? Write a short analysis. Context: {context[:1000]}",
            "conclusion": f"Write a punchy conclusion for {topic} asking the reader for their opinion."
        }

        sections = {}
        for key, prompt in prompts.items():
            sections[key] = query_model({"inputs": prompt, "parameters": {"max_length": 400, "min_length": 100}})
            time.sleep(2) # Rate limit

        return sections

    def format_article(self, topic, sections, images, video):
        title = f"{topic}: Why Everyone is Talking About It (2026)"
        
        # Markdown Construction
        md = f"# {title}\n\n"
        md += f"**{sections['intro']}**\n\n"
        
        if images:
            img = images[0]
            md += f"![{img['alt_description']}]({img['urls']['regular']})\n*Photo by {img['user']['name']} on Unsplash*\n\n"
        
        md += "## The Full Story\n"
        md += f"{sections['body']}\n\n"
        
        if video:
            vid_id = video['id']['videoId']
            md += f"[![Watch Video](https://img.youtube.com/vi/{vid_id}/0.jpg)](https://www.youtube.com/watch?v={vid_id})\n\n"
        
        md += "## Why It Matters\n"
        md += f"{sections['impact']}\n\n"
        
        if len(images) > 1:
            img = images[1]
            md += f"![{img['alt_description']}]({img['urls']['regular']})\n\n"
            
        md += "## Conclusion\n"
        md += f"{sections['conclusion']}\n\n"
        md += "---\n*Generated by AutoBlogger AI*"
        
        # Add Internal Links (Retention)
        related_links = ""
        if len(self.history) > 0:
            related_links = "<h3>Read More:</h3><ul>"
            count = 0
            for item in reversed(self.history):
                if count >= 2: break
                related_links += f"<li>{item['topic']}</li>" 
                count += 1
            related_links += "</ul>"

        # Add Share Buttons (Viral Reach)
        share_html = f"""
        <div style="margin-top: 20px; padding: 15px; background-color: #f0f0f0; border-radius: 5px;">
            <h3>Share this insight:</h3>
            <a href="https://twitter.com/intent/tweet?text={title}&url=URL_PLACEHOLDER" target="_blank" style="margin-right: 10px;">Share on X</a>
            <a href="https://wa.me/?text={title} URL_PLACEHOLDER" target="_blank">Share on WhatsApp</a>
        </div>
        """

        # HTML Construction (Basic)
        html = md.replace("# ", "<h1>").replace("## ", "<h2>").replace("\n\n", "<p>")
        
        # Inject Share Buttons & Related Links before the end
        html += related_links + share_html

        # Add Schema & Meta
        schema = seo_utils.generate_schema(topic, sections['intro'])
        meta = seo_utils.generate_meta_tags(topic, sections['intro'])
        html = meta + schema + html

        return title, md, html

    def publish(self, title, md, html, topic):
        if self.dry_run:
            self.logger.info("DRY RUN: Skipping publish.")
            with open("dry_run_article.md", "w") as f:
                f.write(md)
            with open("dry_run_article.html", "w") as f:
                f.write(html)
            return

        published_url = "URL_PLACEHOLDER"

        # Hashnode (Using requests instead of graphql-requests)
        if self.hashnode_pat:
            try:
                query = """
                mutation PublishStory($input: PublishStoryInput!) {
                  publishStory(input: $input) {
                    success
                    post { url }
                  }
                }
                """
                final_md = md.replace("URL_PLACEHOLDER", "this post") 
                variables = {
                    "input": {
                        "title": title,
                        "contentMarkdown": final_md,
                        "tags": [{"_id": "56744721958ef13879b94c7e", "slug": "technology", "name": "Technology"}], # Simplified tags
                        "isDraft": False
                    }
                }
                
                resp = requests.post(
                    "https://api.hashnode.com",
                    json={'query': query, 'variables': variables},
                    headers={
                        "Authorization": self.hashnode_pat,
                        "Content-Type": "application/json"
                    }
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('data', {}).get('publishStory', {}).get('success'):
                        published_url = data['data']['publishStory']['post']['url']
                        self.logger.info(f"Published to Hashnode: {published_url}")
                    else:
                        self.logger.error(f"Hashnode publish failed: {data}")
                else:
                    self.logger.error(f"Hashnode HTTP failed: {resp.status_code} - {resp.text}")
                    
            except Exception as e:
                self.logger.error(f"Hashnode publish failed: {e}")

        # Dev.to
        if self.devto_key:
            try:
                # FIXED: Wrapped in 'article'
                payload = {
                    "article": {
                        "title": title,
                        "body_markdown": md.replace("URL_PLACEHOLDER", ""),
                        "published": True,
                        "tags": ["news", "trending", "tech"]
                    }
                }
                res = requests.post("https://dev.to/api/articles", json=payload, headers={"api-key": self.devto_key})
                if res.status_code in [200, 201]:
                    url = res.json()['url']
                    self.logger.info(f"Published to Dev.to: {url}")
                    if published_url == "URL_PLACEHOLDER": published_url = url
                else:
                    self.logger.error(f"Dev.to publish failed: {res.status_code} - {res.text}")
            except Exception as e:
                self.logger.error(f"Dev.to publish failed: {e}")

        # Blogger
        if self.creds and self.blog_id:
            try:
                service = build('blogger', 'v3', credentials=self.creds)
                # Inject real URL into share buttons if available
                final_html = html.replace("URL_PLACEHOLDER", published_url if published_url != "URL_PLACEHOLDER" else "")
                post = {'title': title, 'content': final_html, 'labels': [topic]}
                res = service.posts().insert(blogId=self.blog_id, body=post).execute()
                self.logger.info(f"Published to Blogger: {res['url']}")
            except Exception as e:
                self.logger.error(f"Blogger publish failed: {e}")

        # Update History
        self.history.append({"topic": topic, "date": datetime.datetime.now().isoformat()})
        utils.save_history(self.history)

    def run(self):
        topic = self.get_trending_topic()
        news = self.fetch_news(topic)
        if not news:
            self.logger.error("No news found. Aborting.")
            return

        images = self.fetch_images(topic)
        video = self.fetch_video(topic)
        
        sections = self.generate_content(topic, news)
        title, md, html = self.format_article(topic, sections, images, video)
        
        self.publish(title, md, html, topic)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Generate content but do not publish")
    args = parser.parse_args()
    
    bot = AutoBlogger(dry_run=args.dry_run)
    bot.run()