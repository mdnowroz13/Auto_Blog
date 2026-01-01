import argparse
import datetime
import random
import time
import requests
import os
import re
import json
import sys
import xml.etree.ElementTree as ET
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import utils
import seo_utils
from traffic_engine import TrafficEngine

# Configuration
# Hard fallback topics in case Google Trends fails (404)
FALLBACK_TOPICS = [
    "Artificial Intelligence Trends 2026",
    "Quantum Computing Breakthroughs",
    "Sustainable Energy Innovations",
    "Space Exploration Updates 2026",
    "Future of Remote Work"
]

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
        self.blog_url = utils.get_env('BLOG_URL', 'https://example.com')
        self.indexnow_key = utils.get_env('INDEXNOW_KEY')
        
        self.traffic_engine = TrafficEngine(
            creds=self.creds, 
            blog_url=self.blog_url, 
            indexnow_key=self.indexnow_key,
            hf_token=self.hf_token
        )
        
        self.validate_env()

    def validate_env(self):
        """Fail fast if critical keys are missing"""
        missing = []
        if not self.news_api_key: missing.append("NEWSAPI_KEY")
        if not self.hf_token: missing.append("HF_TOKEN")
        if missing:
            self.logger.error(f"Missing critical env vars: {', '.join(missing)}")
            sys.exit(1)

    def _authenticate_google(self):
        SCOPES = ['https://www.googleapis.com/auth/youtube.readonly', 'https://www.googleapis.com/auth/blogger', 'https://www.googleapis.com/auth/webmasters']
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    self.logger.warning(f"Token refresh failed: {e}. Deleting invalid token.json.")
                    if os.path.exists('token.json'):
                        os.remove('token.json')
                    creds = None
            
            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
                    if self.dry_run:
                        self.logger.warning("Skipping Google Auth in dry-run mode.")
                        return None
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    self.logger.error(f"Google Auth failed: {e}")
                    return None
            
            if creds:
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
        return creds

    def get_trending_topics(self):
        self.logger.info("Fetching trending topics (Source: Google News RSS)...")
        topics = []
        
        # 1. Google News RSS (Curated Tech Headlines)
        try:
            # "TECHNOLOGY" Topic Feed - Much higher quality than a generic search
            rss_url = "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en"
            resp = requests.get(rss_url, timeout=10)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for item in root.findall('.//item'):
                    title = item.find('title').text
                    clean_title = title.split(' - ')[0] # Remove source
                    topics.append(clean_title)
        except Exception as e:
            self.logger.error(f"RSS Fetch failed: {e}")

        # 2. NewsAPI Top Headlines (Backup)
        if not topics and self.news_api_key:
             self.logger.info("RSS failed. Trying NewsAPI Headlines...")
             try:
                 url = f"https://newsapi.org/v2/top-headlines?category=technology&language=en&apiKey={self.news_api_key}"
                 resp = requests.get(url, timeout=10)
                 data = resp.json()
                 for article in data.get('articles', [])[:5]:
                     topics.append(article['title'])
             except Exception as e:
                 self.logger.error(f"NewsAPI Headlines failed: {e}")

        if topics:
            random.shuffle(topics)
            # Filter duplicates
            unique_topics = [t for t in topics if not utils.is_duplicate_topic(t, self.history)]
            if unique_topics:
                return unique_topics[:15]
        
        self.logger.warning("No fresh trends found. Using fallback.")
        return FALLBACK_TOPICS

    def fetch_news(self, topic):
        self.logger.info(f"Fetching news for {topic}...")
        from_date = (datetime.date.today() - datetime.timedelta(days=2)).isoformat()
        
        def get_articles(query):
            url = f"https://newsapi.org/v2/everything?q={query}&from={from_date}&sortBy=relevancy&apiKey={self.news_api_key}"
            try:
                resp = requests.get(url)
                data = resp.json()
                return data.get('articles', [])
            except:
                return []

        # 1. Try exact topic match
        articles = get_articles(topic)
        
        # 2. If no results, try first 4 words (Simpler Query)
        if not articles:
            simplified_topic = " ".join(topic.split()[:4])
            self.logger.info(f"No news for exact match. Retrying with: '{simplified_topic}'")
            articles = get_articles(simplified_topic)
            
        return [f"{a['title']}: {a['description']}" for a in articles[:10] if a['description']]

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
            self.logger.error(f"YouTube failed: {e}")
        return None

    def generate_content(self, topic, news_snippets):
        self.logger.info("Generating viral content...")
        headers = {
            "Authorization": f"Bearer {self.hf_token}",
            "Content-Type": "application/json"
        }
        
        # Supported Models (Router Endpoint)
        models = [
            "facebook/bart-large-cnn",
            "google/flan-t5-large",
            "sshleifer/distilbart-cnn-12-6"
        ]

        def validate_content(text, topic):
            """Ensure content is relevant and NOT instructional"""
            if not text: return False
            
            # 1. Check for instructional phrases (Meta-talk)
            instructional_phrases = [
                "here is a blog", "write a blog", "in this article", 
                "sure, i can", "i will explain", "output only", 
                "instruction:", "prompt:"
            ]
            text_lower = text.lower()
            if any(phrase in text_lower for phrase in instructional_phrases):
                self.logger.warning(f"Rejected content due to instructional phrases: {text[:50]}...")
                return False

            # 2. Check for topic relevance
            keywords = [w.lower() for w in topic.split() if len(w) > 3]
            return any(k in text_lower for k in keywords)

        def query_model(prompt, is_retry=False):
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 300, # Increased for better quality
                    "do_sample": False
                }
            }
            
            for model_name in models:
                api_url = f"https://router.huggingface.co/hf-inference/models/{model_name}"
                self.logger.info(f"Trying model: {model_name} (Retry: {is_retry})...")
                
                try:
                    resp = requests.post(api_url, headers=headers, json=payload, timeout=30)
                    
                    if resp.status_code == 200:
                        result = resp.json()
                        text = ""
                        if isinstance(result, list) and len(result) > 0:
                            text = result[0].get('summary_text') or result[0].get('generated_text')
                        
                        if text:
                            # Content Validation
                            if validate_content(text, topic):
                                return text
                            elif not is_retry:
                                self.logger.warning(f"Content validation failed for {model_name}. Regenerating...")
                                # Recursive retry with STRICTER prompt
                                strict_prompt = f"OUTPUT ONLY THE ARTICLE TEXT. NO INSTRUCTIONS. NO META-TALK. Topic: {topic}. {prompt}"
                                return query_model(strict_prompt, is_retry=True)
                            else:
                                self.logger.warning(f"Content validation failed again in {model_name}. Using result anyway.")
                                return text 
                        else:
                            self.logger.warning(f"Empty response from {model_name}")
                    else:
                        self.logger.warning(f"Model Error ({model_name}): {resp.status_code} - {resp.text}")
                        
                except Exception as e:
                    self.logger.error(f"Request failed for {model_name}: {e}")
                
                time.sleep(2)
            
            self.logger.error("All models failed. Aborting content generation.")
            return None

        context = " ".join(news_snippets[:8])
        
        # STRICT PROMPTS - No "Write a..." instructions that confuse the model
        prompts = {
            "intro": f"Topic: {topic}. Context: {context[:500]}. Output a professional, engaging introduction paragraph for a blog post. Start directly with the hook. Do not say 'Here is an intro'.",
            "body": f"Topic: {topic}. Context: {context[:800]}. Output 3 detailed paragraphs explaining the key developments, technical details, and why this matters. Use professional tone. Do not use bullet points. Do not say 'Here is the body'.",
            "impact": f"Topic: {topic}. Context: {context[:500]}. Output a short analysis of the future impact and consequences. Focus on 2026 predictions. Do not say 'Here is the analysis'.",
            "conclusion": f"Topic: {topic}. Output a concluding paragraph summarizing the main point and asking the reader a thought-provoking question. Do not say 'In conclusion'."
        }

        sections = {}
        for key, prompt in prompts.items():
            result = query_model(prompt)
            if result is None:
                return None
            sections[key] = result
            time.sleep(2)

        return sections

    def format_article(self, topic, sections, images, video):
        title = f"{topic}: Why Everyone is Talking About It (2026)"
        
        # Base Markdown Construction
        md_base = f"# {title}\n\n"
        md_base += f"**{sections['intro']}**\n\n"
        
        # Generate & Inject Summary
        summary_html = self.traffic_engine.generate_summary(sections['body'])
        
        if images:
            img = images[0]
            md_base += f"![{img['alt_description']}]({img['urls']['regular']})\n*Photo by {img['user']['name']} on Unsplash*\n\n"
        
        md_base += "## The Full Story\n"
        md_base += f"{sections['body']}\n\n"
        
        # Generate & Inject FAQ
        faq_html = self.traffic_engine.generate_faq(sections['body'])
        
        md_base += "## Why It Matters\n"
        md_base += f"{sections['impact']}\n\n"
        
        if len(images) > 1:
            img = images[1]
            md_base += f"![{img['alt_description']}]({img['urls']['regular']})\n\n"
            
        md_base += "## Conclusion\n"
        md_base += f"{sections['conclusion']}\n\n"
        md_base += "---\n"
        
        # Add Internal Links
        related_posts = self.traffic_engine.find_related_posts(topic, self.history)
        
        md_links = ""
        if related_posts:
            md_links = "\n\n### Read More:\n"
            for p in related_posts:
                md_links += f"- [{p['topic']}]({p.get('url', '#')})\n"
        
        md_base += md_links

        # Add Share Buttons
        share_html = f"""
        <div style="margin-top: 20px; padding: 15px; background-color: #f0f0f0; border-radius: 5px;">
            <h3>Share this insight:</h3>
            <a href="https://twitter.com/intent/tweet?text={title}&url=URL_PLACEHOLDER" target="_blank" style="margin-right: 10px;">Share on X</a>
            <a href="https://wa.me/?text={title} URL_PLACEHOLDER" target="_blank">Share on WhatsApp</a>
        </div>
        """

        # --- Platform Specific Formatting ---

        # 1. Dev.to (Liquid Tags for Video)
        md_devto = md_base
        if video:
            vid_id = video['id']['videoId']
            # Insert video after intro (before "The Full Story")
            insert_point = "**\n\n"
            if insert_point in md_devto:
                parts = md_devto.split(insert_point)
                md_devto = parts[0] + insert_point + f"{{% youtube {vid_id} %}}\n\n" + parts[1]
            else:
                md_devto += f"\n\n{{% youtube {vid_id} %}}"

        # 2. Hashnode (Magic Embeds)
        md_hashnode = md_base
        if video:
            vid_id = video['id']['videoId']
            vid_url = f"https://www.youtube.com/watch?v={vid_id}"
            # Insert video after intro
            insert_point = "**\n\n"
            if insert_point in md_hashnode:
                parts = md_hashnode.split(insert_point)
                md_hashnode = parts[0] + insert_point + f"%[{vid_url}]\n\n" + parts[1]
            else:
                md_hashnode += f"\n\n%[{vid_url}]"

        # 3. Blogger (Robust HTML Construction)
        html = md_base
        
        # Convert Headers (Regex with Multiline)
        html = re.sub(r'^# (.*?)$', r"<h1 style='font-family: Arial, sans-serif; color: #333;'>\1</h1>", html, flags=re.MULTILINE)
        html = re.sub(r'^## (.*?)$', r"<h2 style='font-family: Arial, sans-serif; color: #444; margin-top: 20px;'>\1</h2>", html, flags=re.MULTILINE)
        
        # Convert Bold
        html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html)
        
        # Convert Images
        html = re.sub(r'!\[(.*?)\]\((.*?)\)', r'<div style="text-align:center; margin: 20px 0;"><img src="\2" alt="\1" style="max-width:100%; height:auto; border-radius:10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" /></div>', html)
        
        # Convert Links
        html = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2" target="_blank" style="color: #007bff; text-decoration: none;">\1</a>', html)

        # Process Paragraphs (Block-based)
        blocks = html.split('\n\n')
        final_html_parts = []
        
        for block in blocks:
            block = block.strip()
            if not block: continue
            
            # If block is already a tag (h1, h2, div), leave it alone
            if block.startswith('<h1') or block.startswith('<h2') or block.startswith('<div'):
                final_html_parts.append(block)
            else:
                # Wrap text in styled paragraph
                final_html_parts.append(f"<p style='font-family: Georgia, serif; font-size: 18px; line-height: 1.6; color: #222; margin-bottom: 20px;'>{block}</p>")
        
        html = "".join(final_html_parts)

        # Insert Video (Iframe)
        if video:
             vid_id = video['id']['videoId']
             iframe = f'<div style="text-align:center; margin: 30px 0; clear: both;"><iframe width="560" height="315" src="https://www.youtube.com/embed/{vid_id}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen style="max-width: 100%;"></iframe></div>'
             # Insert after the first paragraph (Intro)
             if "</p>" in html:
                 html = html.replace("</p>", "</p>" + iframe, 1)
             else:
                 html += iframe
        
        html = self.traffic_engine.inject_internal_links(html, related_posts)
        
        # Inject Summary & FAQ into HTML
        # Summary after Intro (first paragraph)
        if summary_html:
            # Simple injection after first </p> if not already done by video
            if "</p>" in html and summary_html not in html:
                 html = html.replace("</p>", "</p>" + summary_html, 1)
            else:
                 html = summary_html + html
                 
        # FAQ before Conclusion
        if faq_html:
             if "<h2>Conclusion</h2>" in html:
                 html = html.replace("<h2>Conclusion</h2>", faq_html + "\n<h2>Conclusion</h2>")
             else:
                 html += faq_html

        html += share_html

        # Add Schema & Meta
        schema = seo_utils.generate_schema(topic, sections['intro'])
        meta = seo_utils.generate_meta_tags(topic, sections['intro'])
        html = meta + schema + html

        return title, md_devto, md_hashnode, html

    def get_hashnode_publication_id(self):
        """Fetch the first publication ID for the user"""
        if not self.hashnode_pat: return None
        
        query = """
        query {
          me {
            publications(first: 1) {
              edges {
                node {
                  id
                  title
                }
              }
            }
          }
        }
        """
        try:
            resp = requests.post(
                "https://gql.hashnode.com",
                json={'query': query},
                headers={
                    "Authorization": self.hashnode_pat,
                    "Content-Type": "application/json"
                }
            )
            data = resp.json()
            if 'errors' in data:
                self.logger.error(f"Hashnode Pub ID Error: {data['errors']}")
                return None
                
            edges = data.get('data', {}).get('me', {}).get('publications', {}).get('edges', [])
            if edges:
                pub_id = edges[0]['node']['id']
                self.logger.info(f"Found Hashnode Publication ID: {pub_id}")
                return pub_id
            else:
                self.logger.warning("No Hashnode publications found.")
                
        except Exception as e:
            self.logger.error(f"Failed to fetch Hashnode Publication ID: {e}")
        return None

    def publish(self, title, md_devto, md_hashnode, html, topic):
        if self.dry_run:
            self.logger.info("DRY RUN: Skipping publish.")
            with open("dry_run_devto.md", "w") as f:
                f.write(md_devto)
            with open("dry_run_hashnode.md", "w") as f:
                f.write(md_hashnode)
            with open("dry_run_article.html", "w") as f:
                f.write(html)
            return

        published_url = "URL_PLACEHOLDER"

        # Hashnode (FIXED SCHEMA & PUBLICATION ID)
        if self.hashnode_pat:
            pub_id = self.get_hashnode_publication_id()
            if pub_id:
                try:
                    query = """
                    mutation PublishPost($input: PublishPostInput!) {
                      publishPost(input: $input) {
                        post {
                          id
                          title
                          slug
                          url
                        }
                      }
                    }
                    """
                    final_md = md_hashnode.replace("URL_PLACEHOLDER", "this post") 
                    variables = {
                        "input": {
                            "title": title,
                            "contentMarkdown": final_md,
                            "publicationId": pub_id,
                            "tags": [{"slug": "technology", "name": "Technology"}]
                        }
                    }
                    
                    resp = requests.post(
                        "https://gql.hashnode.com",
                        json={'query': query, 'variables': variables},
                        headers={
                            "Authorization": self.hashnode_pat,
                            "Content-Type": "application/json"
                        }
                    )
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        if 'errors' in data:
                             self.logger.error(f"Hashnode API Errors: {data['errors']}")
                        elif data.get('data', {}).get('publishPost', {}).get('post'):
                            post_data = data['data']['publishPost']['post']
                            published_url = post_data['url']
                            post_id = post_data['id']
                            self.logger.info(f"Published to Hashnode: {published_url}")
                            
                            # Boost
                            utils.random_delay(10, 30)
                            self.traffic_engine.boost_hashnode(post_id, pub_id, self.hashnode_pat)
                        else:
                            self.logger.error(f"Hashnode publish failed (Unknown response): {data}")
                    else:
                        self.logger.error(f"Hashnode HTTP failed: {resp.status_code} - {resp.text}")
                        
                except Exception as e:
                    self.logger.error(f"Hashnode publish failed: {e}")
            else:
                self.logger.error("Skipping Hashnode: Could not fetch Publication ID")

        # Dev.to
        if self.devto_key:
            try:
                payload = {
                    "article": {
                        "title": title,
                        "body_markdown": md_devto.replace("URL_PLACEHOLDER", ""),
                        "published": True,
                        "tags": ["news", "trending", "tech"]
                    }
                }
                res = requests.post("https://dev.to/api/articles", json=payload, headers={"api-key": self.devto_key})
                if res.status_code in [200, 201]:
                    data = res.json()
                    url = data['url']
                    article_id = data['id']
                    self.logger.info(f"Published to Dev.to: {url}")
                    if published_url == "URL_PLACEHOLDER": published_url = url
                    
                    # Boost
                    utils.random_delay(10, 30)
                    self.traffic_engine.boost_devto(article_id, self.devto_key)
                else:
                    self.logger.error(f"Dev.to publish failed: {res.status_code} - {res.text}")
            except Exception as e:
                self.logger.error(f"Dev.to publish failed: {e}")

        # Blogger
        if self.creds and self.blog_id:
            try:
                service = build('blogger', 'v3', credentials=self.creds)
                final_html = html.replace("URL_PLACEHOLDER", published_url if published_url != "URL_PLACEHOLDER" else "")
                post = {'title': title, 'content': final_html, 'labels': [topic]}
                res = service.posts().insert(blogId=self.blog_id, body=post).execute()
                self.logger.info(f"Published to Blogger: {res['url']}")
            except Exception as e:
                self.logger.error(f"Blogger publish failed: {e}")

        # Traffic Generation
        if published_url and published_url != "URL_PLACEHOLDER":
            self.traffic_engine.submit_to_gsc(published_url)
            self.traffic_engine.ping_services(published_url)
            self.traffic_engine.trigger_indexnow(published_url)

        # Update History
        self.history.append({
            "topic": topic, 
            "date": datetime.datetime.now().isoformat(),
            "url": published_url
        })
        utils.save_history(self.history)

    def republish_cycle(self):
        """Check for old posts and re-submit/boost them."""
        self.logger.info("Running Re-Publish Cycle...")
        cutoff = datetime.datetime.now() - datetime.timedelta(days=7)
        
        candidates = []
        for entry in self.history:
            try:
                entry_date = datetime.datetime.fromisoformat(entry['date'])
                if entry_date < cutoff:
                    candidates.append(entry)
            except: pass
                
        if not candidates:
            self.logger.info("No old posts to republish.")
            return

        # Pick one random old post
        post = random.choice(candidates)
        url = post.get('url')
        if not url or url == "URL_PLACEHOLDER":
            return

        self.logger.info(f"Republishing/Boosting old post: {post['topic']} ({url})")
        
        # 1. Re-Submit to Indexing
        self.traffic_engine.submit_to_gsc(url)
        self.traffic_engine.ping_services(url)
        self.traffic_engine.trigger_indexnow(url)

    def run(self):
        topics = self.get_trending_topics()
        
        for topic in topics:
            self.logger.info(f"Attempting to blog about: {topic}")
            news = self.fetch_news(topic)
            if news:
                images = self.fetch_images(topic)
                video = self.fetch_video(topic)
                
                sections = self.generate_content(topic, news)
                if sections:
                    title, md_devto, md_hashnode, html = self.format_article(topic, sections, images, video)
                    self.publish(title, md_devto, md_hashnode, html, topic)
                    
                    # Run Re-Publish Cycle
                    self.republish_cycle()
                    
                    # Generate Analytics Report
                    utils.generate_analytics_report()
                    return # Success!
                else:
                    self.logger.warning(f"Content generation failed for {topic}. Trying next topic...")
            else:
                self.logger.warning(f"No news found for {topic}. Trying next topic...")
        
        self.logger.error("Failed to generate a blog post for any trending topic.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Generate content but do not publish")
    args = parser.parse_args()
    
    bot = AutoBlogger(dry_run=args.dry_run)
    bot.run()