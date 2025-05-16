from flask import Flask, redirect, request, session, url_for, render_template
import praw
import os
from dotenv import load_dotenv
from collections import Counter
from datetime import datetime
from pymongo import MongoClient

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDDIT_REDIRECT_URI", "https://rediit-analysis-4.onrender.com/reddit_analysis_callback")

# Replace with your actual MongoDB connection string
MONGO_URI = "mongodb+srv://ankushraina24:Ankush2003@testsocialmedia.uuo8yht.mongodb.net/"
client = MongoClient(MONGO_URI)
db = client['Reddit_data']  # Replace 'socialmedia' with your actual database name
reddit_collection = db["Reddit-analysic"]

# Step 1: Home Page
@app.route('/')
def index():
    return redirect(url_for('login'))


# Step 2: Redirect to Reddit login
@app.route('/login')
def login():
    reddit = praw.Reddit(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        user_agent="OAuthRedditAnalytics/0.1"
    )
    auth_url = reddit.auth.url(["identity", "history", "read"], "random_state", "permanent")
    return redirect(auth_url)


# Step 3: Handle Reddit callback
@app.route('/reddit_analysis_callback')
def reddit_analysis_callback():
    code = request.args.get("code")
    if not code:
        return "Authorization failed", 400

    reddit = praw.Reddit(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        user_agent="OAuthRedditAnalytics/0.1"
    )

    refresh_token = reddit.auth.authorize(code)
    session['refresh_token'] = refresh_token
    return redirect(url_for('dashboard'))


# Step 4: Show Dashboard with Analytics
@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'refresh_token' not in session:
        return redirect(url_for('index'))

    reddit = praw.Reddit(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        user_agent="OAuthRedditAnalytics/0.1",
        refresh_token=session['refresh_token']
    )

    # Get username from query string or use logged-in user
    username = request.args.get('username')
    if username:
        redditor = reddit.redditor(username)
    else:
        redditor = reddit.user.me()
        username = redditor.name

    # Fetch submissions for the user
    submissions = list(redditor.submissions.new(limit=50))  # Fetch more to get top 5

    # Sort by score and get top 6
    top_posts = sorted(submissions, key=lambda s: s.score, reverse=True)[:6]

    posts_with_comments = []
    total_likes = 0
    total_comments = 0
    for post in top_posts:
        post.comments.replace_more(limit=0)
        comments = post.comments.list()[:5]  # Top 5 comments
        posts_with_comments.append({
            "title": post.title,
            "subreddit": str(post.subreddit),
            "score": post.score,
            "url": post.url,
            "permalink": f"https://reddit.com{post.permalink}",
            "content": post.selftext,
            "created_utc": post.created_utc,
            "comments": [{"body": c.body, "score": c.score} for c in comments]
        })
        total_likes += post.score
        total_comments += len(comments)

    for post in posts_with_comments:
        reddit_collection.insert_one({
            "user": username,
            "title": post["title"],
            "subreddit": post["subreddit"],
            "content": post["content"],
            "likes": post["score"],
            "permalink": post["permalink"],
            "comments": post["comments"],
            "num_comments": len(post["comments"]),
            "created_utc": post["created_utc"]
        })

    return render_template("dashboard.html", username=username, posts=posts_with_comments, total_likes=total_likes, total_comments=total_comments)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.template_filter('datetimeformat')
def datetimeformat(value):
    try:
        return datetime.utcfromtimestamp(float(value)).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return value


if __name__ == '__main__':
    app.run(debug=True,port=5000)
