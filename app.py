import requests
from flask import Flask, render_template
import random

#create python list of subreddits from where memes will be extracted using API
with open('subreddits.txt', 'r') as f:
    subreddits_list = f.read().splitlines()

MEME_API_URL = "https://meme-api.com/gimme/"
MEME_API_TIMEOUT = (2, 3)


# Fetch once; the caller handles upstream failures without retrying.
def getMeme():
    """Fetch and validate one meme, raising on upstream or payload errors."""
    subreddit = random.choice(subreddits_list)
    with requests.get(
        MEME_API_URL + subreddit, timeout=MEME_API_TIMEOUT, allow_redirects=False
    ) as response:
        response.raise_for_status()
        res = response.json()

    subreddit_name = res["subreddit"]
    previews = res["preview"]
    if not isinstance(previews, list):
        raise ValueError("Invalid meme previews")
    img_max = previews[-1]
    if not isinstance(subreddit_name, str) or not subreddit_name:
        raise ValueError("Invalid subreddit")
    if not isinstance(img_max, str) or not img_max.startswith(("https://", "http://")):
        raise ValueError("Invalid meme image")
    return img_max, subreddit_name


app = Flask(__name__)

@app.route('/')
def index():
    """Render a meme or return an unavailable page with HTTP 503."""
    try:
        meme_img, subreddit = getMeme()
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        app.logger.warning("Meme API request failed", exc_info=True)
        return render_template("meme_index.html", unavailable=True), 503
    return render_template("meme_index.html", meme_pic = meme_img, subreddit = subreddit)


#lightweight health check that does not call the meme API
@app.route('/health')
def health():
    """Report readiness without contacting the meme API."""
    return {"status": "ok"}


if __name__ == '__main__':
    app.run()
