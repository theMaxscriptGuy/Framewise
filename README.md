# Framewise

Framewise is a Python + Qt5 video review tool. It lets you load a video, scrub frame-by-frame, add markups, attach comments per frame, and save/load reviews as JSON.

## Features
- Load video files and scrub frame-by-frame
- Draw pen or rectangle markups on any frame
- Write comments per frame
- Save and load reviews as JSON

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Notes
- Reviews store the original `video_path`, so keep the video file accessible when reloading a review.
- JSON review files include comments and markups per frame.

## Demo
https://youtu.be/VbyyQMpwgbg
