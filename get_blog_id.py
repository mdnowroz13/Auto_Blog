from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os

def get_blog_id():
    SCOPES = ['https://www.googleapis.com/auth/blogger']
    
    if not os.path.exists('token.json'):
        print("Error: token.json not found.")
        return

    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    service = build('blogger', 'v3', credentials=creds)

    try:
        # Get user's blogs
        blogs = service.blogs().listByUser(userId='self').execute()
        if 'items' in blogs:
            print("\nFound your blogs:")
            for blog in blogs['items']:
                print(f"Name: {blog['name']}")
                print(f"URL: {blog['url']}")
                print(f"BLOG_ID: {blog['id']}") # This is what we need
                print("-" * 20)
        else:
            print("No blogs found for this account.")
            
    except Exception as e:
        print(f"Error fetching blogs: {e}")

if __name__ == "__main__":
    get_blog_id()
