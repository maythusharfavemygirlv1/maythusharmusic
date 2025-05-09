import asyncio
import re
import yt_dlp
from typing import Union
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="

    async def _get_ydl_options(self, audio=False):
        """အသံ/ဗီဒီယို download settings များ"""
        return {
            "format": "bestaudio/best" if audio else "bestvideo[height<=720]+bestaudio/best",
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

    async def exists(self, link: str):
        """လင့်ခ်အမှန်အကန်စစ်ဆေးခြင်း"""
        return re.search(self.regex, link) is not None

    async def extract_url(self, message: Message):
        """Message မှ YouTube URL ထုတ်ယူခြင်း"""
        for entity in (message.entities or message.caption_entities or []):
            if entity.type == MessageEntityType.URL:
                return (message.text or message.caption)[entity.offset:entity.offset+entity.length]
            elif entity.type == MessageEntityType.TEXT_LINK:
                return entity.url
        return None

    async def get_details(self, link: str):
        """ဗီဒီယိုအသေးစိတ်အချက်အလက်များ"""
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return {
                "title": result["title"],
                "duration": result["duration"],
                "thumbnail": result["thumbnails"][0]["url"].split("?")[0],
                "vidid": result["id"],
                "url": self.base + result["id"]
            }
        return None

    async def download_content(self, link: str, audio=False):
        """အဓိက download လုပ်သည့် function"""
        ydl_opts = await self._get_ydl_options(audio)
        
        def sync_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                filename = ydl.prepare_filename(info)
                if not os.path.exists(filename):
                    ydl.download([link])
                return filename

        return await asyncio.get_event_loop().run_in_executor(None, sync_download)

    async def get_stream_url(self, link: str, audio=False):
        """တိုက်ရိုက်ဖွင့်ကြည့်နိုင်သော URL ရယူခြင်း"""
        ydl_opts = await self._get_ydl_options(audio)
        ydl_opts["skip_download"] = True
        
        def extract_url():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                return info.get("url")

        return await asyncio.get_event_loop().run_in_executor(None, extract_url)

    async def playlist_videos(self, playlist_url: str, limit=10):
        """Playlist မှဗီဒီယိုများရယူခြင်း"""
        ydl_opts = {
            "extract_flat": True,
            "force_ipv4": True,
            "geo_bypass": True,
        }
        
        def get_playlist():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
                return [
                    {
                        "title": entry["title"],
                        "url": self.base + entry["id"],
                        "duration": entry.get("duration"),
                        "thumbnail": f"https://i.ytimg.com/vi/{entry['id']}/hqdefault.jpg"
                    } for entry in info["entries"][:limit]
                ]
                
        return await asyncio.get_event_loop().run_in_executor(None, get_playlist)

# Example Usage
async def main():
    yt = YouTubeAPI()
    
    # ဗီဒီယိုအချက်အလက်များရယူခြင်း
    url = "https://youtu.be/FU0rtCL1Lkw?si=fE6tAbnq3oRCLBLv"
    details = await yt.get_details(url)
    print(f"Video Title: {details['title']}")

    # အသံဖိုင်ဒေါင်းလုဒ်လုပ်ခြင်း (320kbps MP3)
    audio_file = await yt.download_content(url, audio=True)
    print(f"Downloaded Audio: {audio_file}")

    # ဗီဒီယိုဖိုင်ဒေါင်းလုဒ်လုပ်ခြင်း (720p MP4)
    video_file = await yt.download_content(url)
    print(f"Downloaded Video: {video_file}")

    # Playlist မှဗီဒီယိုစာရင်းရယူခြင်း
    playlist = await yt.playlist_videos("https://youtube.com/playlist?list=fE6tAbnq3oRCLBLv")
    print(f"Playlist Videos: {len(playlist)}")

if __name__ == "__main__":
    asyncio.run(main())
