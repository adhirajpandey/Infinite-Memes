# Infinite-Memes
This repository contains a simple Python Web Dev Project, which is a meme webapp built with Flask, HTML and CSS which fetches memes from one of the random subreddits from predefined lists using meme API. 

The page refreshes automatically every 15 seconds to get new memes. The website is responsive, allowing users to watch memes in their free time in any device. The project has been deployed using Render cloud service provider, the link is provided below.

Check it out - https://memes.adhirajpandey.me/

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Installing

1. Clone the repository to your machine using the following command:

    `git clone https://github.com/adhirajpandey/Infinite-Memes`


2. Once the repository is cloned, you can install the necessary packages by running the following command:

    `pip install -r requirements.txt`

### Running the application

To run the flask application, execute the following command: `python app.py`

`GET /health` returns `{"status": "ok"}` without calling the meme API. Use it for health and readiness checks.

Each page request makes one meme API request, with a 2-second connection timeout
and a 3-second read timeout. Failures and invalid responses return HTTP 503 with
a message; the page refreshes again after 15 seconds. Redirects are not followed.
The read timeout limits how long the connection can go without receiving data;
it is not a deadline for the whole request.

The container runs Gunicorn with one worker and four threads, using
`gunicorn.conf.py`. A slow meme request can occupy a thread while another serves
`/health`. If all four threads are busy, health requests still have to wait.
For the same behavior outside Docker, run
`gunicorn --config gunicorn.conf.py --bind 127.0.0.1:8000 app:app`.

### Tests

With the dependencies installed, run `python -m unittest discover -s tests -v`.
The tests use mocked responses and a local HTTP server, including a Gunicorn
check that requests `/health` while the meme API is stalled. They do not call
the public meme API.

`requirements.txt` keeps setuptools below version 81 because the pinned Gunicorn
version imports `pkg_resources`.

### Deploying this change

Rebuild the image to include the application and Gunicorn configuration, then
recreate the container. For installations with a standby host, prepare the same
version on both hosts before updating the active container. Keep readiness checks
pointed at `/health`.


## Features to be added

* Fetches list of subreddits from a database.
* Add post link on the webpage and provide redirection link to post and subreddit as well.

## Sample

![image](https://user-images.githubusercontent.com/87516052/213318553-14f938ce-f537-4a12-8350-9c5636852330.png)
