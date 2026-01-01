from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import os

def authenticate_google():
    SCOPES = ['https://www.googleapis.com/auth/youtube.readonly', 'https://www.googleapis.com/auth/blogger']
    creds = None
    
    # Check if token.json already exists
    if os.path.exists('token.json'):
        print("token.json already exists! You are good to go.")
        return

    # Check if credentials.json exists
    if not os.path.exists('credentials.json'):
        print("ERROR: credentials.json not found!")
        print("Please download it from Google Cloud Console and put it in this folder.")
        return

    print("Starting Google Login...")
    try:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
        print("\nSUCCESS! 🌟")
        print("token.json has been created.")
        print("Now open token.json, copy EVERYTHING inside it, and add it to GitHub Secrets as 'GOOGLE_TOKEN_JSON'.")
        
    except Exception as e:
        print(f"\nAuth failed: {e}")
        print("Make sure you added your email to 'Test Users' in Google Cloud Console!")

if __name__ == "__main__":
    authenticate_google()
