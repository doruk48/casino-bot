# modules/music/player.py - GÜNCELLENDİ
import asyncio
import os
import logging
from typing import Optional, Dict
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioFile, AudioParameters

logger = logging.getLogger(__name__)

class MusicPlayer:
    def __init__(self, app):
        self.app = app
        self.call_client: Optional[PyTgCalls] = None
        self.active_calls: Dict[int, dict] = {}
        self.volumes: Dict[int, int] = {}          # 🆕 Ses seviyesi
        self.current_info: Dict[int, dict] = {}    # 🆕 Çalan şarkı bilgisi
        self._ready = False
    
    async def start(self):
        if self._ready:
            return
        self.call_client = PyTgCalls(self.app)
        await self.call_client.start()
        self._ready = True
        logger.info("🎵 Müzik motoru başlatıldı")
    
    async def stop(self):
        if self.call_client:
            for chat_id in list(self.active_calls.keys()):
                try:
                    await self.call_client.leave_group_call(chat_id)
                except:
                    pass
            self.active_calls.clear()
            self.current_info.clear()
            self._ready = False
    
    async def play(self, chat_id: int, file_path: str, title: str = "Bilinmeyen") -> bool:
        if not self._ready:
            return False
        
        try:
            if chat_id in self.active_calls:
                await self.stop_chat(chat_id)
            
            await self.call_client.join_group_call(chat_id)
            
            vol = self.volumes.get(chat_id, 80)
            await self.call_client.play(
                chat_id,
                AudioPiped(file_path, AudioParameters(bitrate=128000))
            )
            
            self.active_calls[chat_id] = {
                'title': title,
                'file': file_path,
                'started': asyncio.get_event_loop().time()
            }
            
            return True
        except Exception as e:
            logger.error(f"Müzik çalma hatası: {e}")
            return False
    
    async def stop_chat(self, chat_id: int) -> bool:
        try:
            if chat_id in self.active_calls:
                await self.call_client.leave_group_call(chat_id)
                del self.active_calls[chat_id]
            return True
        except:
            return False
    
    def is_playing(self, chat_id: int) -> bool:
        return chat_id in self.active_calls
    
    def get_current(self, chat_id: int) -> Optional[str]:
        if chat_id in self.current_info:
            return self.current_info[chat_id].get('title')
        return None
