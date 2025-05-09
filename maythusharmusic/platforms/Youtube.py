import asyncio
import os
import random
import re
import logging
from typing import Tuple, Union, List, Dict

from async_lru import alru_cache
from youtubesearchpython.__future__ import VideosSearch
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

import config
from maythusharmusic.utils.database import is_on_off
from maythusharmusic.utils.decorators import asyncify
from maythusharmusic.utils.formatters import seconds_to_min, time_to_seconds
from cailin import cookies  # Cookie ဖိုင်မှ Cookie များကို ဖတ်ရန်

# Logger သတ်မှတ်ခြင်း
logger = logging.getLogger(__name__)
NOTHING = {"cookies_dead": None}  # Cookie status သိမ်းဆည်းရန်

async def shell_cmd(cmd: str) -> str:
    """Shell command များကို run ရန် function"""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    
    try:
        output = stdout.decode("utf-8") if stdout else ""
        error = stderr.decode("utf-8") if stderr else ""
    except UnicodeDecodeError:
        output = stdout.decode("latin-1") if stdout else ""
        error = stderr.decode("latin-1") if stderr else ""

    if proc.returncode != 0:
        logger.error(f"Shell command မအောင်မြင်ပါ: {error.strip()}")
        if "unavailable videos are hidden" in error.lower():
            return output
        return error
    return output

class YouTube:
    """YouTube နှင့်ဆိုင်သော အဓိက function များ"""
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="

    async def exists(self, link: str, videoid: bool = False) -> bool:
        """Link သည် YouTube link ဟုတ်မဟုတ်စစ်ဆေးခြင်း"""
        try:
            if videoid:
                link = self.base + link
            return bool(re.search(self.regex, link))
        except Exception as e:
            logger.error(f"Link စစ်ဆေးရာတွင်အမှာ့: {str(e)}")
            return False

    @property
    def use_fallback(self) -> bool:
        """Cookie များအသုံးမပြုနိုင်ပါက fallback သုံးရန်"""
        return NOTHING["cookies_dead"] is True

    @use_fallback.setter
    def use_fallback(self, value: bool):
        NOTHING["cookies_dead"] = value

    @asyncify
    def url(self, message: Message) -> Union[str, None]:
        """Message မှ YouTube URL ထုတ်ယူခြင်း"""
        try:
            entities = message.entities or message.caption_entities
            if not entities:
                return None

            for entity in entities:
                if entity.type == MessageEntityType.URL:
                    text = message.text or message.caption
                    return text[entity.offset:entity.offset + entity.length]
                elif entity.type == MessageEntityType.TEXT_LINK:
                    return entity.url
            return None
        except Exception as e:
            logger.error(f"URL ထုတ်ယူရာတွင်အမှာ့: {str(e)}")
            return None

    @alru_cache(maxsize=None)
    async def details(self, link: str, videoid: bool = False) -> Tuple:
        """ဗီဒီယို၏ အသေးစိတ်အချက်အလက်များရယူခြင်း"""
        try:
            if videoid:
                link = self.base + link
            link = link.split("&")[0]  # Query parameters ဖယ်ရှား

            results = VideosSearch(link, limit=1)
            search_results = await results.next()
            if not search_results["result"]:
                return (None,) * 5

            result = search_results["result"][0]
            return (
                result.get("title", "ခေါင်းစဥ်မရှိ"),
                result.get("duration", "0:00"),
                int(time_to_seconds(result.get("duration", "0:00"))),
                result.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
                result.get("id", "")
            )
        except Exception as e:
            logger.error(f"အသေးစိတ်ရယူရာတွင်အမှာ့: {str(e)}")
            return (None,) * 5

    # ကျန်သော function များကို အောက်တွင်ဆက်လက်ထည့်သွင်းထားပါသည်...

    @alru_cache(maxsize=None)
    async def track(self, query: str, videoid: bool = False) -> Tuple[Dict, str]:
        """သီချင်းရှာဖွေရန် (VideosSearch နှင့် yt-dlp နှစ်မျိုးသုံး)"""
        try:
            link = self.base + query if videoid else query
            results = VideosSearch(link, limit=1)
            search_results = await results.next()
            
            if search_results["result"]:
                result = search_results["result"][0]
                return ({
                    "title": result["title"],
                    "link": result["link"],
                    "vidid": result["id"],
                    "duration_min": result.get("duration"),
                    "thumb": result["thumbnails"][0]["url"].split("?")[0]
                }, result["id"])
            
            # Fallback to yt-dlp ဖြင့်ရှာဖွေခြင်း
            return await self._track(query)
        except Exception as e:
            logger.error(f"Track ရှာဖွေရာတွင်အမှာ့: {str(e)}")
            return await self._track(query)

    @asyncify
    def _track(self, query: str) -> Tuple[Dict, str]:
        """yt-dlp ဖြင့် backup search"""
        try:
            with YoutubeDL({"quiet": True, "cookiefile": cookies()}) as ydl:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)
                if not info or not info.get("entries"):
                    return {}, ""
                
                entry = info["entries"][0]
                return ({
                    "title": entry["title"],
                    "link": entry["url"],
                    "vidid": entry["id"],
                    "duration_min": seconds_to_min(entry["duration"]) if entry.get("duration") else None,
                    "thumb": entry.get("thumbnails", [{}])[0].get("url", "")
                }, entry["id"])
        except Exception as e:
            logger.error(f"Backup search တွင်အမှာ့: {str(e)}")
            return {}, ""

    @alru_cache(maxsize=None)
    @asyncify
    def formats(self, link: str, videoid: bool = False) -> Tuple[List[Dict], str]:
        """ဗီဒီယို၏ format များစာရင်းရယူခြင်း"""
        try:
            if videoid:
                link = self.base + link
            ydl_opts = {"quiet": True, "cookiefile": cookies()}
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                formats = []
                
                for f in info.get("formats", []):
                    try:
                        formats.append({
                            "format": f.get("format"),
                            "filesize": f.get("filesize"),
                            "format_id": f.get("format_id"),
                            "ext": f.get("ext"),
                            "format_note": f.get("format_note"),
                            "yturl": link
                        })
                    except KeyError:
                        continue
                return formats, link
        except Exception as e:
            logger.error(f"Formats ရယူရာတွင်အမှာ့: {str(e)}")
            return [], link

    @alru_cache(maxsize=None)
    async def slider(self, link: str, query_type: int, videoid: bool = False) -> Tuple:
        """ဆက်စပ်ဗီဒီယိုများရယူခြင်း"""
        try:
            if videoid:
                link = self.base + link
            search = VideosSearch(link, limit=10)
            results = (await search.next())["result"]
            
            result = results[query_type]
            return (
                result.get("title", "ခေါင်းစဥ်မရှိ"),
                result.get("duration", "0:00"),
                result.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
                result.get("id", "")
            )
        except IndexError:
            return ("", "", "", "")
        except Exception as e:
            logger.error(f"Slider ရယူရာတွင်အမှာ့: {str(e)}")
            return ("", "", "", "")

    async def download(
        self,
        link: str,
        mystic: Message,
        video: bool = False,
        videoid: bool = False,
        songaudio: bool = False,
        songvideo: bool = False,
        format_id: str = None,
        title: str = None
    ) -> Union[str, Tuple[str, str]]:
        """Media များဒေါင်းလုပ်ဆွဲရန် အဓိက function"""
        try:
            if videoid:
                link = self.base + link

            # Download directory စစ်ဆေးခြင်း
            os.makedirs("downloads", exist_ok=True)

            @asyncify
            def _audio_dl():
                """အသံဖိုင်ဒေါင်းလုပ်ဆွဲရန်"""
                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": "downloads/%(id)s.%(ext)s",
                    "cookiefile": cookies(),
                    "geo_bypass": True,
                    "nocheckcertificate": True,
                    "quiet": True,
                    "no_warnings": True,
                }
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=False)
                    path = ydl.prepare_filename(info)
                    if os.path.exists(path):
                        return path
                    ydl.download([link])
                    return path

            @asyncify
            def _video_dl():
                """ဗီဒီယိုဖိုင်ဒေါင်းလုပ်ဆွဲရန်"""
                ydl_opts = {
                    "format": "(bestvideo[height<=720][ext=mp4])+(bestaudio[ext=m4a])",
                    "outtmpl": "downloads/%(id)s.%(ext)s",
                    "cookiefile": cookies(),
                    "merge_output_format": "mp4",
                    "geo_bypass": True,
                    "nocheckcertificate": True,
                    "quiet": True,
                    "no_warnings": True,
                }
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=False)
                    path = ydl.prepare_filename(info)
                    if os.path.exists(path):
                        return path
                    ydl.download([link])
                    return path

            # လိုအပ်သော download type ကိုရွေးချယ်ခြင်း
            if songvideo:
                # သီချင်းဗီဒီယို download လုပ်ခြင်း
                return await _video_dl()
            elif songaudio:
                # သီချင်းအသံဖိုင် download လုပ်ခြင်း
                return await _audio_dl()
            elif video:
                # သာမန်ဗီဒီယို download လုပ်ခြင်း
                return await _video_dl()
            else:
                # သာမန်အသံဖိုင် download လုပ်ခြင်း
                return await _audio_dl()

        except DownloadError as e:
            logger.error(f"Download မအောင်မြင်ပါ: {str(e)}")
            await mystic.edit_text(f"ဒေါင်းလုပ်ဆွဲရာတွင်အမှာ့: {str(e)}")
            return ""
        except Exception as e:
            logger.error(f"Download process error: {str(e)}")
            await mystic.edit_text(f"အမှားတစ်ခုဖြစ်သွားပါသည်: {str(e)}")
            return ""
