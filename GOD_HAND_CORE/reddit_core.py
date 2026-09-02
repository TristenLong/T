import os

import praw
from dotenv import load_dotenv

ROOT_ENV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(ROOT_ENV, override=True)

def get_reddit_client():
    try:
        client_id = os.getenv('REDDIT_CLIENT_ID')
        client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        user_agent = os.getenv('REDDIT_USER_AGENT', 'JESTER_V081_AGENT/1.0')

        if not client_id or not client_secret:
            return None, "REDDIT_CREDENTIALS_MISSING"

        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        return reddit, "OK"
    except Exception as e:
        return None, str(e)

def scan_subreddit(sub_name, limit=3):
    reddit, status = get_reddit_client()
    if not reddit:
        return f"ERROR: Could not connect to Reddit. {status}"

    try:
        subreddit = reddit.subreddit(sub_name)
        posts = []
        for post in subreddit.hot(limit=limit):
            posts.append(f"TITLE: {post.title}\nID: {post.id}\nSCORE: {post.score}\nCONTENT: {post.selftext[:500]}...")
        
        return "\n---\n".join(posts)
    except Exception as e:
        return f"ERROR: Failed to scan r/{sub_name}. {str(e)}"

if __name__ == "__main__":
    print(scan_subreddit("technology"))
