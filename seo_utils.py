import json
import datetime

def generate_schema(topic, description, author_name="AutoBlogger", image_url=None):
    """Generate JSON-LD Schema for the article."""
    schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": f"{topic}: What You Need to Know",
        "image": [image_url] if image_url else [],
        "datePublished": datetime.datetime.now().isoformat(),
        "author": {
            "@type": "Person",
            "name": author_name
        },
        "description": description
    }
    return f'<script type="application/ld+json">{json.dumps(schema)}</script>'

def generate_meta_tags(topic, summary):
    """Generate HTML meta tags for SEO."""
    # Extract a punchy description from the summary (first 150 chars)
    desc = summary[:155] + "..." if len(summary) > 155 else summary
    tags = f"""
    <meta name="description" content="{desc}">
    <meta name="keywords" content="{topic}, trending, news, {datetime.datetime.now().year}">
    <meta property="og:title" content="{topic}: Deep Dive">
    <meta property="og:description" content="{desc}">
    <meta property="og:type" content="article">
    """
    return tags

def inject_seo_keywords(text, topic, keywords):
    """
    Simple keyword injection. 
    Ensures the topic and related keywords appear in headers.
    """
    # This is a placeholder for more advanced NLP injection
    # For now, we rely on the prompt to include them, but we can enforce H2 changes here
    return text
