import asyncio
import os
import re
import json
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from maythusharmusic.utils.database import is_on_off
from maythusharmusic.utils.formatters import time_to_seconds

import os
import glob
import random
import logging

def cookie_txt_file():
    folder_path = f"{os.getcwd()}/cookies"
    filename = f"{os.getcwd()}/cookies/logs.csv"
    txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
    if not txt_files:
        raise FileNotFoundError("No .txt files found in the specified folder.")
    cookie_txt_file = random.choice(txt_files)
    with open(filename, 'a') as file:
        file.write(f'Choosen File : {cookie_txt_file}\n')
    return f"cookies/{str(cookie_txt_file).split('/')[-1]}"

async def check_file_size(link):
    async def get_format_info(link):
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f'Error:\n{stderr.decode()}')
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None
    
    formats = info.get('formats', [])
    if not formats:
        print("No formats found.")
        return None
    
    total_size = parse_size(formats)
    return total_size

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

return {
            "format": "bestaudio/best" if audio else          
            "bestvideo[height<=720]+bestaudio/best",
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "geo_bypass": True,
            "geo_bypass_country": "US",
            "force_ipv4": True,
            "nocheckcertificate": True,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320"
                }
            ] if audio else [],
            "postprocessor_args": ["-metadata", "title=%(title)s"],
        }
    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return re.search(self.regex, link) is not None

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        
        for message in messages:
            # Check entities first
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset:entity.offset + entity.length]
            # Then check caption entities
            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return (
                result["title"],
                result["duration"],
                int(time_to_seconds(result["duration"])),
                result["thumbnails"][0]["url"].split("?")[0],
                result["id"]
            )
        return None, None, None, None, None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        title, _, _, _, _ = await self.details(link, videoid)
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        _, duration, _, _, _ = await self.details(link, videoid)
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        _, _, _, thumbnail, _ = await self.details(link, videoid)
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
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
        return (1, stdout.decode().split("\n")[0]) if stdout else (0, stderr.decode())

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        )
        return [x for x in playlist.split("\n") if x.strip()]

    async def track(self, link: str, videoid: Union[bool, str] = None):
        title, duration, vidid, thumbnail, _ = await self.details(link, videoid)
        return {
            "title": title,
            "link": self.base + vidid,
            "vidid": vidid,
            "duration_min": duration,
            "thumb": thumbnail,
        }, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        ytdl_opts = {"quiet": True, "cookiefile": cookie_txt_file()}
        with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            return [
                {
                    "format": f["format"],
                    "filesize": f.get("filesize", 0),
                    "format_id": f["format_id"],
                    "ext": f["ext"],
                    "format_note": f.get("format_note", ""),
                    "yturl": link,
                }
                for f in info["formats"]
                if not "dash" in f["format"].lower()
            ], link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        results = (await VideosSearch(link, limit=10).next())["result"]
        result = results[query_type]
        return (
            result["title"],
            result["duration"],
            result["thumbnails"][0]["url"].split("?")[0],
            result["id"]
        )

    async def download(self, link: str, mystic, video=False, videoid=None, songaudio=False, songvideo=False, format_id=None, title=None):
        if videoid:
            link = self.base + link

        loop = asyncio.get_running_loop()

        # 320kbps Audio Downloader
        def audio_dl():
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "geo_bypass_country": "US",
                "force_ipv4": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }],
                "postprocessor_args": ["-metadata", f"title={title}", "-metadata", "artist=MayThuSharMusic"],
                "embedthumbnail": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                path = ydl.prepare_filename(info)
                ydl.process_info(info)
            return path.replace(".webm", ".mp3").replace(".m4a", ".mp3")

        # High Quality Video Downloader
        def video_dl():
            ydl_opts = {
                "format": "bestvideo[height<=720]+bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "geo_bypass_country": "US",
                "force_ipv4": True,
                "cookiefile": cookie_txt_file(),
                "merge_output_format": "mp4",
                "postprocessor_args": {"prefer_ffmpeg": True},
                "writethumbnail": True,
                "embedthumbnail": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.download([link])

        # Song Specific Downloads
        def song_specific_dl():
            ydl_opts = {
                "format": f"{format_id}+bestaudio" if songvideo else format_id,
                "outtmpl": f"downloads/{title}.%(ext)s",
                "cookiefile": cookie_txt_file(),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "320",
                    }
                ] if songaudio else [],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
            return f"downloads/{title}.{'mp4' if songvideo else 'mp3'}"

        # Main download logic
        if songvideo or songaudio:
            return await loop.run_in_executor(None, song_specific_dl)
        elif video:
            return await loop.run_in_executor(None, video_dl)
        else:
            return await loop.run_in_executor(None, audio_dl)

# Usage Example
if __name__ == "__main__":
    api = YouTubeAPI()
    result = asyncio.run(api.download("https://youtu.be/...", None))
    print(f"Downloaded file: {result}")
