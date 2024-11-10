from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
from moviepy.editor import VideoFileClip
import os

# Replace 'your_bot_token' with your actual Telegram bot token
BOT_TOKEN = os.environ.get("tk")
API_ID = int(os.environ.get("apiid")) # Replace with your API ID
API_HASH = os.environ.get("apihash")  # Replace with your API Hash

# Initialize the Pyrogram client
app = Client("yt_downloader_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# Global variables for tracking progress and current action
progress = 0
tasks={}
current_action = "Idle"  # Will store "Downloading" or "Uploading"
prb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Check Progress", callback_data="progress")]
    ])


COOKIES_FILE_PATH = "cookies.txt"

def set_cookie(cookie_text):
    """
    Saves the provided cookie text to a file in the format expected by yt-dlp.
    """
    with open(COOKIES_FILE_PATH, "w") as f:
        f.write(cookie_text)

    print("Cookies have been set.")

# Function to update the global progress variable during download/upload
async def update_progress(client, callback_query, current, total, action):
    global progress, current_action
    progress = int(current * 100 / total)
    current_action = action
        
def download_hook(d):
    global progress, current_action

    if d['status'] == 'downloading':
        progress = d.get('downloaded_bytes', 0) / d.get('total_bytes', 1) * 100
        current_action = "Downloading"
    elif d['status'] == 'finished':
        progress = 100
        current_action = "Download complete"

# Function to download YouTube video with progress tracking
def download_video(url, resolution):
    global progress, current_action

    ydl_opts = {
        'format': f'bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]',
        'outtmpl': f'{resolution}_video.mp4',
        'quiet': True,
        'progress_hooks': [download_hook],  # Add progress hook
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            current_action = "Starting download"
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            return file_path
    except Exception as e:
        print(f"Error downloading video: {e}")
        return None
# Function to generate a thumbnail at 3 seconds
def generate_thumbnail(video_path):
    thumbnail_path = "thumbnail.jpg"
    try:
        with VideoFileClip(video_path) as clip:
            clip.save_frame(thumbnail_path, t=3)  # Capture at 3 seconds
        return thumbnail_path
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return None

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Hello! Send a YouTube link and choose a resolution to download the video.")

@app.on_message(filters.command("pr"))
async def progress_report(client, message):
    global progress, current_action
    await message.reply_text(f"{current_action}... {progress}%" if current_action != "Idle" else "No active download/upload.")
        
@app.on_message(filters.command("setcookie"))
async def set_cookie_command(client, message):
    cookie_text = message.text.replace("/setcookie ", "", 1)
    if not cookie_text:
        await message.reply_text("Please provide the cookie text after the /setcookie command.")
        return
    set_cookie(cookie_text)
    await message.reply_text(f"Cookies have been set successfully.\n\n{cookie_text}")

#@app.on_message(filters.text & filters.private)
@app.on_message(filters.regex(pattern=".*http.*"))
async def youtube_download(client, message):
    global tasks
    url = message.text
    tasks[message.from_user.id] = url
    await message.reply_text(
        "Choose a resolution:", 
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("1080p", callback_data=f"1080p_")],
            [InlineKeyboardButton("720p", callback_data=f"720p_")],
            [InlineKeyboardButton("480p", callback_data=f"480p_")],
            [InlineKeyboardButton("360p", callback_data=f"360p_")],
            [InlineKeyboardButton("240p", callback_data=f"360p_")]
        ])
    )

@app.on_callback_query()
async def button_callback(client, callback_query):
  global progress, current_action
  if "_" in callback_query.data:
    data = callback_query.data.split("_")
    resolution = data[0] #,url = data[0], "_".join(data[1:])
    if callback_query.from_user.id in tasks:
        url = tasks[callback_query.from_user.id]
        #await callback_query.answer("Downloading...", show_alert=True)
        await callback_query.message.edit_text("Downloading......",reply_markup=prb)

        current_action = "Downloading"
        file_path = download_video(url, resolution)
    
        if file_path:
           # Notify that download is complete and upload is starting
           await callback_query.message.edit_text("Download complete. Uploading...",reply_markup=prb)
           current_action = "Uploading"
           thumbnail_path = generate_thumbnail(file_path)
           async def upload_progress(current, total):
               await update_progress(client, callback_query, current, total, "Uploading")
           await client.send_video(
               chat_id=callback_query.message.chat.id,
               video=file_path,
               thumb=thumbnail_path,
               supports_streaming=True,
               progress=upload_progress
               )
           os.remove(file_path)
           if thumbnail_path:
             os.remove(thumbnail_path)
           progress = 0
           current_action = "Idle"
           tasks.pop(callback_query.from_user.id, None)
           await callback_query.message.delete()
        else:
           await callback_query.message.edit_text("The requested resolution is not available for this video.")
    else:
       await callback_query.message.edit_text("Downloading......",reply_markup=prb)

  else:
    if "pr" in callback_query.data:
      await callback_query.answer(f"{current_action}... {progress}%" if current_action != "Idle" else "No active download/upload.",show_alert=True)
    elif "del" in callback_query.data:
      await callback_query.message.delete()
app.run()
