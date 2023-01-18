import requests
from flask import Flask, render_template
import random

#list of subreddits from where memes will be extracted using API
subreddits_list = ["funny", "memes", "comedyheaven", "raimimemes", "okbuddyretard", "dankmemes", "terriblefacebookmemes", "DankExchange", "wholesomememes", "dankinindia", "TheRealJoke"]

#function to get a random meme from randomly selected subreddit from the list
def getMeme():
    
    subreddit = subreddits_list[random.randint(0, len(subreddits_list) - 1)]
    
    try:
        url = "https://meme-api.com/gimme/" + subreddit
        res = requests.get(url).json()
        
        subreddit_name = res["subreddit"]
        
        #to get link of highest quality of image
        img_max = res["preview"][-1]

        return img_max, subreddit_name
    except:
        return getMeme()


app = Flask(__name__)

@app.route('/')
def index():
    meme_img , subreddit = getMeme()
    return render_template("meme_index.html", meme_pic = meme_img, subreddit = subreddit)


if __name__ == '__main__':
    app.run()