import requests
import json
import logging
import urllib.parse
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import utils

logger = logging.getLogger(__name__)

class TrafficEngine:
    def __init__(self, creds=None, blog_url=None, indexnow_key=None, hf_token=None):
        self.creds = creds
        self.blog_url = blog_url
        self.indexnow_key = indexnow_key
        self.hf_token = hf_token
        self.search_console = None
        
        if self.creds:
            try:
                self.search_console = build('searchconsole', 'v1', credentials=self.creds)
            except Exception as e:
                logger.error(f"Failed to init Search Console: {e}")

    def submit_to_gsc(self, url):
        """Submit a URL to Google Search Console for indexing."""
        if not self.search_console:
            logger.warning("GSC not initialized. Skipping submission.")
            return False

        logger.info(f"Submitting to Google Search Console: {url}")
        try:
            # 1. Inspect URL (Optional, to check status)
            # 2. Submit (Publish) - Note: The API technically supports 'inspect', 
            # but direct 'submit' is limited. We use the 'sites.add' or sitemap submission 
            # usually. However, for individual URL indexing, the Indexing API is for Job/Broadcast.
            # For general blogs, we should submit the sitemap or use 'inspect' to request indexing (if supported via API).
            # ACTUALLY: The standard GSC API allows sitemap submission. 
            # The "Indexing API" is strictly for JobPosting/BroadcastEvent.
            # We will submit the sitemap as the primary method, as it's safer.
            
            # However, we can use the 'urlInspection' to check.
            # For this 'Auto Indexing' requirement, we'll submit the sitemap 
            # which contains the new URL.
            
            sitemap_url = f"{self.blog_url}/sitemap.xml"
            self.search_console.sitemaps().submit(siteUrl=self.blog_url, feedpath=sitemap_url).execute()
            logger.info(f"Sitemap submitted: {sitemap_url}")
            return True
            
        except HttpError as e:
            logger.error(f"GSC Submission failed: {e}")
            return False
        except Exception as e:
            logger.error(f"GSC Error: {e}")
            return False

    def ping_services(self, url):
        """Ping various services to notify them of updates."""
        logger.info(f"Pinging services for: {url}")
        
        services = [
            f"http://www.google.com/ping?sitemap={self.blog_url}/sitemap.xml",
            f"http://www.bing.com/ping?sitemap={self.blog_url}/sitemap.xml",
            "http://rpc.twingly.com/"
        ]
        
        for service in services:
            try:
                requests.get(service, timeout=5)
                logger.info(f"Pinged: {service}")
            except Exception as e:
                logger.warning(f"Failed to ping {service}: {e}")

    def trigger_indexnow(self, url):
        """Trigger IndexNow to instantly notify Bing and Yandex."""
        if not self.indexnow_key:
            logger.warning("IndexNow key missing. Skipping.")
            return False
            
        logger.info(f"Triggering IndexNow for: {url}")
        
        # IndexNow Endpoint (Bing)
        endpoint = "https://api.indexnow.org/indexnow"
        
        payload = {
            "host": urllib.parse.urlparse(self.blog_url).netloc,
            "key": self.indexnow_key,
            "keyLocation": f"{self.blog_url}/{self.indexnow_key}.txt",
            "urlList": [url]
        }
        
        try:
            headers = {"Content-Type": "application/json; charset=utf-8"}
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=10)
            
            if resp.status_code in [200, 202]:
                logger.info("IndexNow submission successful.")
                return True
            else:
                logger.error(f"IndexNow failed: {resp.status_code} - {resp.text}")
                return False
                
        except Exception as e:
            logger.error(f"IndexNow Error: {e}")
            return False

    def find_related_posts(self, current_topic, history, limit=3):
        """Find related posts from history based on keyword overlap."""
        if not history:
            return []
            
        current_keywords = set(current_topic.lower().split())
        scored_posts = []
        
        for entry in history:
            # Skip if it's the same topic (fuzzy match) or very recent
            if entry['topic'] == current_topic:
                continue
                
            # Calculate overlap
            entry_keywords = set(entry['topic'].lower().split())
            overlap = len(current_keywords.intersection(entry_keywords))
            
            if overlap > 0:
                scored_posts.append((overlap, entry))
                
        # Sort by overlap desc
        scored_posts.sort(key=lambda x: x[0], reverse=True)
        
        return [p[1] for p in scored_posts[:limit]]

    def inject_internal_links(self, html_content, related_posts):
        """Inject internal links into the HTML content."""
        if not related_posts:
            return html_content
            
        links_html = "<div class='internal-links' style='margin: 30px 0; padding: 20px; background: #f9f9f9; border-left: 5px solid #007bff;'>"
        links_html += "<h3>Read More on this Topic:</h3><ul>"
        
        for post in related_posts:
            # Assuming history has 'url' or we construct it. 
            # If 'url' is missing, we might need to skip or use a search URL.
            # For now, we'll assume 'url' is present in history updates.
            url = post.get('url', '#')
            title = post.get('topic', 'Related Article')
            links_html += f"<li><a href='{url}' target='_blank'>{title}</a></li>"
            
        links_html += "</ul></div>"
        
        # Inject before the "Conclusion" or at the end
        if "<h2>Conclusion</h2>" in html_content:
            return html_content.replace("<h2>Conclusion</h2>", links_html + "\n<h2>Conclusion</h2>")
        else:
            return html_content + links_html

    def boost_hashnode(self, post_id, publication_id, pat):
        """Auto-bookmark and comment on Hashnode post."""
        if not pat or not post_id:
            return
            
        logger.info(f"Boosting Hashnode Post: {post_id}")
        headers = {
            "Authorization": pat,
            "Content-Type": "application/json"
        }
        
        # 1. Add to Reading List (Bookmark) - Note: API might not expose this directly for 'me', 
        # but we can try to 'react' to it.
        # Mutation: toggleReaction(id: ID!, reaction: ReactionType!)
        
        query_react = """
        mutation ToggleReaction($id: ID!, $reaction: ReactionType!) {
          toggleReaction(id: $id, reaction: $reaction) {
            reaction
          }
        }
        """
        # Reactions: CLAP, THUMBS_UP, HEART, etc.
        # We'll add a HEART and a CLAP
        for reaction in ["HEART", "CLAP"]:
            try:
                requests.post("https://gql.hashnode.com", json={
                    'query': query_react, 
                    'variables': {'id': post_id, 'reaction': reaction}
                }, headers=headers)
            except: pass
            
        # 2. Add a Comment
        # Mutation: replyToPost(postId: ID!, contentMarkdown: String!)
        query_comment = """
        mutation ReplyToPost($postId: ID!, $content: String!) {
          replyToPost(input: {postId: $postId, contentMarkdown: $content}) {
            reply {
              id
            }
          }
        }
        """
        
        comments = [
            "Great insights! I'm really looking forward to seeing how this evolves in 2026.",
            "This is a crucial topic. Thanks for breaking it down so clearly!",
            "Interesting perspective. Do you think this will impact the industry sooner than expected?"
        ]
        
        import random
        comment = random.choice(comments)
        
        try:
            requests.post("https://gql.hashnode.com", json={
                'query': query_comment,
                'variables': {'postId': post_id, 'content': comment}
            }, headers=headers)
            logger.info("Added comment to Hashnode post.")
        except Exception as e:
            logger.error(f"Hashnode Comment failed: {e}")

    def boost_devto(self, article_id, api_key):
        """Auto-comment on Dev.to post."""
        if not api_key or not article_id:
            return
            
        logger.info(f"Boosting Dev.to Article: {article_id}")
        
        # Dev.to Comments API: POST /api/comments
        # Payload: { "comment": { "body_markdown": "...", "commentable_id": 123, "commentable_type": "Article" } }
        
        comments = [
            "Awesome read! 🚀",
            "Thanks for sharing this! 🔥",
            "Really helpful summary. Bookmarked! 🔖"
        ]
        import random
        comment = random.choice(comments)
        
        url = "https://dev.to/api/comments"
        payload = {
            "comment": {
                "body_markdown": comment,
                "commentable_id": article_id,
                "commentable_type": "Article"
            }
        }
        
        try:
            resp = requests.post(url, json=payload, headers={"api-key": api_key})
            if resp.status_code in [200, 201]:
                logger.info("Added comment to Dev.to article.")
            else:
                logger.warning(f"Dev.to comment failed: {resp.status_code}")
        except Exception as e:
            logger.error(f"Dev.to boosting failed: {e}")

    def generate_faq(self, content):
        """Generate FAQ using LLM."""
        if not self.hf_token or not content:
            return ""
            
        logger.info("Generating FAQ...")
        # Using a simpler model for instruction following if possible, or careful prompting
        prompt = f"Generate 3 Frequently Asked Questions (FAQ) with short answers based on this text. Output HTML details/summary tags. Text: {content[:1500]}"
        
        faq = utils.query_huggingface(prompt, self.hf_token, model="facebook/bart-large-cnn")
        if faq:
            return f"<div class='faq-section' style='margin-top: 30px;'><h3>Frequently Asked Questions</h3>{faq}</div>"
        return ""

    def generate_summary(self, content):
        """Generate short summary."""
        if not self.hf_token or not content:
            return ""
            
        logger.info("Generating Summary...")
        prompt = f"Summarize this text in 2 sentences: {content[:1500]}"
        
        summary = utils.query_huggingface(prompt, self.hf_token, model="facebook/bart-large-cnn")
        if summary:
            return f"<div class='article-summary' style='background: #f0f8ff; padding: 15px; border-radius: 5px; margin-bottom: 20px; border-left: 5px solid #007bff;'><strong>Quick Summary:</strong> {summary}</div>"
        return ""
