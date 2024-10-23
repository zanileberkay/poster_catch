import os
import sys
import json
import requests
from PIL import Image
from moviepy.editor import VideoFileClip
import subprocess
import praw

# Constants and Setup
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)
CONFIG_PATH = 'options.json'
CREDENTIALS_PATH = 'credentials.py'  # Assuming a Python file for simplicity

# Load Credentials (Assuming a simple Python file with REDDIT_CREDENTIALS dict)
with open(CREDENTIALS_PATH, 'r') as f:
    exec(f.read())  # Loads REDDIT_CREDENTIALS into the scope

def load_options():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def authenticate_reddit():
    return praw.Reddit(
        client_id=REDDIT_CREDENTIALS['client_id'],
        client_secret=REDDIT_CREDENTIALS['client_secret'],
        user_agent=REDDIT_CREDENTIALS['user_agent']
    )

def download_media(url, download_path, submission=None):
    response = requests.get(url)
    if response.status_code == 200:
        with open(download_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded: {download_path}")
        if submission:
            save_caption(submission, download_path)
    else:
        print(f"Failed to download {url}")

def download_video(url, output_file, submission=None):
    success = download_reddit_video(url, output_file)
    if not success:
        print(f"Failed to download video for post {submission.id if submission else 'unknown'}")
    else:
        if submission:
            save_caption(submission, output_file)
        print(f"Downloaded video with audio: {output_file}")

def download_reddit_video(url, output_file):
    try:
        cmd = [
            'yt-dlp',
            '-f', 'bestvideo+bestaudio/best',
            '--merge-output-format','mp4',
            '-o', output_file,
            url
        ]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"youtube-dl log: {result.stdout}")
        if os.path.exists(output_file):
            print(f"Successfully downloaded video using youtube-dl: {output_file}")
            return True
    except subprocess.CalledProcessError as e:
        print(f"youtube-dl failed: {e}")
        print(f"youtube-dl error log: {e.output}")
        
        try:
            video_url = f"{url}/DASH_1080.mp4"
            audio_url = f"{url}/DASH_audio.mp4"
            
            video_file = f"{output_file}_temp_video.mp4"
            audio_file = f"{output_file}_temp_audio.mp4"
            
            subprocess.run(['ffmpeg', '-i', video_url, '-c', 'copy', video_file], check=True)
            subprocess.run(['ffmpeg', '-i', audio_url, '-c', 'copy', audio_file], check=True)
            
            subprocess.run([
                'ffmpeg', '-i', video_file, '-i', audio_file,
                '-c', 'copy', '-map', '0:v:0', '-map', '1:a:0', output_file
            ], check=True)
            
            print(f"Successfully downloaded video using FFmpeg fallback: {output_file}")
            
            os.remove(video_file)
            os.remove(audio_file)
            return True
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg fallback failed: {e}")
            return False
    except Exception as e:
        print(f"Unexpected error in download_reddit_video: {e}")
        return False

def save_caption(submission, filename):
    filename_only = os.path.basename(filename)
    caption_path = os.path.join('data', 'downloaded', f"{os.path.splitext(filename_only)[0]}.txt")
    with open(caption_path, 'w', encoding='utf-8') as f:
        f.write(submission.title)
        if submission.selftext:
            f.write('\n\n' + submission.selftext)

def standardize_image_instagram_aspect_ratio(input_path, output_path):
    with Image.open(input_path) as img:
        width, height = img.size
        target_ratio = 4 / 5  
        if width / height > target_ratio:
            new_height = int(width / target_ratio)
            new_img = Image.new('RGB', (width, new_height), color='black')
            y_offset = (new_height - height) // 2
            new_img.paste(img, (0, y_offset))
        else:
            new_width = int(height * target_ratio)
            new_img = Image.new('RGB', (new_width, height), color='black')
            x_offset = (new_width - width) // 2
            new_img.paste(img, (x_offset, 0))
        new_img.save(output_path, 'JPEG')
        print(f"Standardized image: {output_path}")

def standardize_video_instagram_aspect_ratio(input_path, output_path):
    with VideoFileClip(input_path) as clip:
        width, height = clip.size
        target_ratio = 4 / 5  
        if width / height > target_ratio:
            new_height = int(width / target_ratio)
            y_padding = (new_height - height) // 2
            padded_clip = clip.margin(top=y_padding, bottom=y_padding, color=(0,0,0))
        else:
            new_width = int(height * target_ratio)
            x_padding = (new_width - width) // 2
            padded_clip = clip.margin(left=x_padding, right=x_padding, color=(0,0,0))
        padded_clip.write_videofile(output_path)
        print(f"Standardized video: {output_path}")

def standardize_image_square_shape(input_path, output_path):
    with Image.open(input_path) as img:
        width, height = img.size
        side_length = max(width, height)
        new_img = Image.new('RGB', (side_length, side_length), color='black')
        if width > height:
            y_offset = (side_length - height) // 2
            new_img.paste(img, (0, y_offset))
        else:
            x_offset = (side_length - width) // 2
            new_img.paste(img, (x_offset, 0))
        new_img.save(output_path, 'JPEG')
        print(f"Standardized image (square shape): {output_path}")

def standardize_video_square_shape(input_path, output_path):
    with VideoFileClip(input_path) as clip:
        width, height = clip.size
        side_length = max(width, height)
        if width > height:
            padding_top = (side_length - height) // 2
            padding_bottom = side_length - height - padding_top
            padding_left = 0
            padding_right = 0
        else:
            padding_top = 0
            padding_bottom = 0
            padding_left = (side_length - width) // 2
            padding_right = side_length - width - padding_left
        new_clip = clip.margin(
            top=padding_top,
            bottom=padding_bottom,
            left=padding_left,
            right=padding_right,
            opacity=0  
        )
        new_clip.write_videofile(output_path)
        print(f"Standardized video (square shape): {output_path}")

def process_media(input_folder, output_folder, standardization_method):
    for filename in os.listdir(input_folder):
        input_path = os.path.join(input_folder, filename)
        output_path = os.path.join(output_folder, filename)
        
        if filename.endswith(('.jpg', '.jpeg', '.png')):
            if standardization_method == "instagram_aspect_ratio":
                standardize_image_instagram_aspect_ratio(input_path, output_path)
            elif standardization_method == "square_shape":
                standardize_image_square_shape(input_path, output_path)
        elif filename.endswith('.mp4'):
            if standardization_method == "instagram_aspect_ratio":
                standardize_video_instagram_aspect_ratio(input_path, output_path)
            elif standardization_method == "square_shape":
                standardize_video_square_shape(input_path, output_path)

def download_posts(subreddits, post_limit, post_timeframe):
    reddit = authenticate_reddit()
    for subreddit_name in subreddits:
        subreddit = reddit.subreddit(subreddit_name)
        for idx, submission in enumerate(subreddit.top(post_timeframe, limit=post_limit), start=1):
            url = submission.url
            if url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                ext = url.split('.')[-1]
                filename = f"{submission.id}.{ext}"
                download_path = os.path.join('data', 'downloaded', filename)
                download_media(url, download_path, submission)
            elif 'v.redd.it' in url or submission.is_video:
                output_file = os.path.join('data', 'downloaded', f"{submission.id}.mp4")
                download_video(url, output_file, submission)

def main():
    options = load_options()
    subreddits = options['subreddits']
    post_timeframe = options['post_timeframe']
    post_limit = options['post_limit']
    standardization_method = options['media_standardization']['method']
    
    os.makedirs('data/downloaded', exist_ok=True)
    os.makedirs('data/standardized', exist_ok=True)

    download_posts(subreddits, post_limit, post_timeframe)
    process_media('data/downloaded', 'data/standardized', standardization_method)

if __name__ == "__main__":
    main()
