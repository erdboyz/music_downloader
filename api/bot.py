import asyncio
import os
import re
import tempfile
from pathlib import Path
import aiohttp
import yt_dlp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

SOUNDCLOUD_REGEX = re.compile(
    r'https?://(?:www\.)?soundcloud\.com/[\w\-\.]+/[\w\-\.]+'
)

class SoundCloudDownloader:
    def __init__(self):
        self.ydl_opts = {
            'format': 'best[ext=mp3]/best[acodec=mp3]/best[abr<=320]/best',
            'outtmpl': '%(title)s.%(ext)s',
            'extractaudio': True,
            'audioformat': 'mp3',
            'audioquality': '192',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'writeinfojson': False,
            'writethumbnail': False,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'referer': 'https://soundcloud.com/',
        }
    
    async def download_track(self, url: str, temp_dir: str) -> tuple[str, dict]:
        loop = asyncio.get_event_loop()
        
        def _download():
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                filename = f"{info.get('title', 'track')}.{info.get('ext', 'mp3')}"
                filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
                filepath = os.path.join(temp_dir, filename)
                
                opts = self.ydl_opts.copy()
                opts['outtmpl'] = filepath
                
                with yt_dlp.YoutubeDL(opts) as ydl_download:
                    ydl_download.download([url])
                
                return filepath, info
        
        return await loop.run_in_executor(None, _download)

downloader = SoundCloudDownloader()

@dp.message(Command("start"))
async def start_handler(message: Message):
    welcome_text = """
🎵 <b>Добро пожаловать в SoundCloud Bot!</b>

Я помогу вам скачать музыку с SoundCloud.

<b>Как использовать:</b>
• Отправьте мне ссылку на трек с SoundCloud
• Я скачаю и отправлю вам аудиофайл

<b>Поддерживаемые форматы ссылок:</b>
• https://soundcloud.com/artist/track-name
• https://www.soundcloud.com/artist/track-name

<b>Команды:</b>
/start - показать это сообщение
/help - помощь

Просто отправьте ссылку, и я начну загрузку! 🎧
    """
    await message.answer(welcome_text)

@dp.message(Command("help"))
async def help_handler(message: Message):
    help_text = """
🆘 <b>Помощь по использованию бота</b>

<b>Как скачать трек:</b>
1. Найдите трек на SoundCloud
2. Скопируйте ссылку на трек
3. Отправьте ссылку мне в чат
4. Дождитесь загрузки и получите аудиофайл

<b>Примеры поддерживаемых ссылок:</b>
• https://soundcloud.com/artist/song
• https://www.soundcloud.com/user/track-name

<b>Ограничения:</b>
• Работаю только с публичными треками
• Размер файла не должен превышать 50MB
• Загрузка может занять несколько минут

<b>Проблемы?</b>
Убедитесь, что ссылка корректная и трек доступен для публичного просмотра.
    """
    await message.answer(help_text)

@dp.message(F.text.regexp(SOUNDCLOUD_REGEX))
async def soundcloud_handler(message: Message):
    url = message.text.strip()
    
    status_message = await message.answer("🔄 <b>Начинаю загрузку...</b>\nПожалуйста, подождите.")
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            await status_message.edit_text("📥 <b>Загружаю трек с SoundCloud...</b>")
            
            filepath, info = await downloader.download_track(url, temp_dir)
            
            if not os.path.exists(filepath):
                await status_message.edit_text("❌ <b>Ошибка:</b> Не удалось загрузить файл.")
                return
            
            file_size = os.path.getsize(filepath)
            
            if file_size > 50 * 1024 * 1024:
                await status_message.edit_text(
                    "❌ <b>Ошибка:</b> Файл слишком большой для отправки через Telegram (>50MB)."
                )
                return
            
            await status_message.edit_text("📤 <b>Отправляю аудиофайл...</b>")
            
            with open(filepath, 'rb') as audio_file:
                audio_data = audio_file.read()
            
            title = info.get('title', 'Неизвестный трек')
            uploader = info.get('uploader', 'Неизвестный исполнитель')
            duration = info.get('duration', 0)
            
            if duration and isinstance(duration, (int, float)):
                duration = int(duration)
                minutes = duration // 60
                seconds = duration % 60
                duration_str = f"{minutes:02d}:{seconds:02d}"
            else:
                duration_str = "Неизвестно"
                duration = None
            
            audio_file_obj = BufferedInputFile(
                audio_data,
                filename=f"{title}.mp3"
            )
            
            caption = f"""
🎵 <b>{title}</b>
👤 <b>Исполнитель:</b> {uploader}
⏱ <b>Длительность:</b> {duration_str}
💾 <b>Размер:</b> {file_size / (1024*1024):.1f} MB

<i>Загружено с SoundCloud</i>
            """.strip()
            
            await message.answer_audio(
                audio=audio_file_obj,
                caption=caption,
                title=title,
                performer=uploader,
                duration=duration if duration else None
            )
            
            await status_message.delete()
            
    except yt_dlp.DownloadError as e:
        logger.error(f"Ошибка yt-dlp при загрузке трека: {e}")
        await status_message.edit_text(
            f"❌ <b>Ошибка загрузки с SoundCloud</b>\n\n"
            f"Возможные причины:\n"
            f"• Трек недоступен или удален\n"
            f"• Трек является приватным\n"
            f"• Проблемы с доступом к SoundCloud\n\n"
            f"Попробуйте другую ссылку или повторите попытку позже."
        )
    except FileNotFoundError:
        logger.error("Загруженный файл не найден")
        await status_message.edit_text(
            "❌ <b>Ошибка:</b> Загруженный файл не найден.\n"
            "Попробуйте еще раз."
        )
    except Exception as e:
        logger.error(f"Неожиданная ошибка при загрузке трека: {e}")
        error_msg = str(e)
        if "format code" in error_msg.lower():
            await status_message.edit_text(
                "❌ <b>Ошибка обработки метаданных трека</b>\n\n"
                "Трек загружен, но возникла проблема с отображением информации.\n"
                "Попробуйте еще раз."
            )
        else:
            await status_message.edit_text(
                f"❌ <b>Произошла неожиданная ошибка</b>\n\n"
                f"Возможные причины:\n"
                f"• Временные проблемы с сервисом\n"
                f"• Проблемы с интернет-соединением\n"
                f"• Неподдерживаемый формат трека\n\n"
                f"Попробуйте еще раз через несколько минут."
            )

@dp.message(F.text)
async def text_handler(message: Message):
    """Обработчик обычного текста"""
    text = message.text.lower()
    
    if any(word in text for word in ['soundcloud', 'ссылка', 'скачать', 'трек']):
        await message.answer(
            "🔗 <b>Отправьте ссылку на SoundCloud</b>\n\n"
            "Пример правильной ссылки:\n"
            "<code>https://soundcloud.com/artist/track-name</code>\n\n"
            "Я смогу скачать только публичные треки!"
        )
    else:
        await message.answer(
            "❓ <b>Не понимаю команду</b>\n\n"
            "Отправьте мне ссылку на трек с SoundCloud, и я его скачаю!\n\n"
            "Используйте /help для получения справки."
        )