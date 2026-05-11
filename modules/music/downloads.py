# modules/music/downloads.py - YouTube'dan Ses İndirme
import os
import tempfile
import logging
import yt_dlp

logger = logging.getLogger(__name__)

async def download_audio(query: str) -> dict:
    """YouTube'dan ses indir, dosya yolunu ve bilgileri döndür"""
    temp_dir = tempfile.mkdtemp()
    output_path = os.path.join(temp_dir, "audio.%(ext)s")
    
    ydl_opts = {
        'format': 'bestaudio[abr<=128]',  # Max 128kbps
        'outtmpl': output_path,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'max_filesize': 20_000_000,  # Max 20MB
        'cookiefile': None,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)
            if 'entries' in info:
                info = info['entries'][0]
            
            file_path = os.path.join(temp_dir, "audio.mp3")
            
            return {
                'file': file_path,
                'title': info.get('title', 'Bilinmeyen'),
                'duration': info.get('duration', 0),
                'url': info.get('webpage_url', ''),
                'temp_dir': temp_dir
            }
    except Exception as e:
        logger.error(f"İndirme hatası: {e}")
        raise
