import asyncio
import os
import re
import json
import glob
import random
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from maythusharmusic.utils.database import is_on_off
from maythusharmusic.utils.formatters import time_to_seconds

def cookie_txt_file():
    current_dir = os.getcwd()
    folder_path = os.path.join(current_dir, "cookies")
    txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
    if not txt_files:
        raise FileNotFoundError("No .txt files found in the cookies directory.")
    chosen_file = random.choice(txt_files)
    logs_path = os.path.join(folder_path, "logs.csv")
    with open(logs_path, 'a') as file:
        file.write(f'Chosen File: {chosen_file}\n')
    return chosen_file

async def check_file_size(link):
    cmd = [
        "yt-dlp",
        "--cookies", cookie_txt_file(),
        "-f", "best[height<=?720][width<=?1280]",
        "--get-filesize",
        link
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return None
    try:
        return int(stdout.decode().strip())
    except ValueError:
        return None

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        error_msg = errorz.decode("utf-8").lower()
        if "unavailable videos are hidden" in error_msg:
            return out.decode("utf-8")
        return error_msg
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return text[offset:offset + length] if offset else None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result.get("duration", "0:00")
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        loop = asyncio.get_event_loop()
        ydl_opts = {
            'format': 'best[height<=?720][width<=?1280]',
            'quiet': True,
            'cookiefile': cookie_txt_file(),
        }
        try:
            def extract_url():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=False)
                    return info['url']
            url = await loop.run_in_executor(None, extract_url)
            return 1, url
        except Exception as e:
            return 0, str(e)

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        loop = asyncio.get_event_loop()
        ydl_opts = {
            'extract_flat': 'in_playlist',
            'playlistend': limit,
            'quiet': True,
            'cookiefile': cookie_txt_file(),
        }
        def extract_playlist():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(link, download=False)
        info = await loop.run_in_executor(None, extract_playlist)
        return [entry['id'] for entry in info.get('entries', []) if entry.get('id')]

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()

        def audio_dl():
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "flac",
                    "preferredquality": "0",
                }],
                "cookiefile": cookie_txt_file(),
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
            return f"downloads/{info['id']}.flac"

        def video_dl():
            ydl_opts = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "cookiefile": cookie_txt_file(),
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
            return f"downloads/{info['id']}.mp4"

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}.mp4"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            with yt_dlp.YoutubeDL(ydl_optssx) as ydl:
                ydl.download([link])
            return fpath

        def song_audio_dl():
            ydl_check = yt_dlp.YoutubeDL({'quiet': True, 'cookiefile': cookie_txt_file()})
            info = ydl_check.extract_info(link, download=False)
            has_flac = any(f.get('ext') == 'flac' for f in info['formats'])

            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": f"downloads/{title}.%(ext)s",
                "cookiefile": cookie_txt_file(),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "flac" if has_flac else "mp3",
                    "preferredquality": "0" if has_flac else "320",
                }],
                "quiet": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
            return f"downloads/{title}.flac" if has_flac else f"downloads/{title}.mp3"

        if songvideo:
            fpath = await loop.run_in_executor(None, song_video_dl)
            return fpath, True
        elif songaudio:
            fpath = await loop.run_in_executor(None, song_audio_dl)
            return fpath, True
        elif video:
            if await is_on_off(1):
                downloaded_file = await loop.run_in_executor(None, video_dl)
                return downloaded_file, True
            else:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--cookies", cookie_txt_file(),
                    "-g",
                    "-f",
                    "best[height<=?720][width<=?1280]",
                    link,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    return stdout.decode().split("\n")[0], False
                else:
                    downloaded_file = await loop.run_in_executor(None, video_dl)
                    return downloaded_file, True
        else:
            downloaded_file = await loop.run_in_executor(None, audio_dl)
            return downloaded_file, True
