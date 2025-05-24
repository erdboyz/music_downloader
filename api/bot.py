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
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging for serverless environment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set")

# Initialize bot and dispatcher
bot = Bot(
    token=BOT_TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# SoundCloud URL regex
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
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'referer': 'https://soundcloud.com/',
            # Add headers to avoid blocking
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip,deflate',
                'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
                'Keep-Alive': '300',
                'Connection': 'keep-alive',
            }
        }
    
    def sanitize_filename(self, filename):
        """Clean filename for cross-platform compatibility."""
        # Remove or replace problematic characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = re.sub(r'[^\w\s\-_\.]', '', filename)
        filename = filename.strip()
        # Ensure filename isn't too long
        if len(filename) > 200:
            filename = filename[:200]
        return filename
    
    async def download_track(self, url: str, temp_dir: str) -> tuple[str, dict]:
        """Download track from SoundCloud."""
        loop = asyncio.get_event_loop()
        
        def _download():
            try:
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    # First, extract info without downloading
                    info = ydl.extract_info(url, download=False)
                    
                    if not info:
                        raise Exception("Could not extract track information")
                    
                    # Clean the title for filename
                    title = info.get('title', 'track')
                    clean_title = self.sanitize_filename(title)
                    
                    # Prepare filename
                    filename = f"{clean_title}.mp3"
                    filepath = os.path.join(temp_dir, filename)
                    
                    # Update options for download
                    download_opts = self.ydl_opts.copy()
                    download_opts['outtmpl'] = filepath
                    
                    # Download the track
                    with yt_dlp.YoutubeDL(download_opts) as ydl_download:
                        ydl_download.download([url])
                    
                    # Check if file was actually created
                    if not os.path.exists(filepath):
                        # Try to find the downloaded file with different extension
                        for ext in ['.mp3', '.m4a', '.opus', '.webm']:
                            alt_path = os.path.join(temp_dir, f"{clean_title}{ext}")
                            if os.path.exists(alt_path):
                                # Rename to .mp3
                                os.rename(alt_path, filepath)
                                break
                        else:
                            raise FileNotFoundError(f"Downloaded file not found: {filepath}")
                    
                    return filepath, info
                    
            except Exception as e:
                logger.error(f"Download error: {e}")
                raise
        
        return await loop.run_in_executor(None, _download)

# Initialize downloader
downloader = SoundCloudDownloader()

@dp.message(Command("start"))
async def start_handler(message: Message):
    """Handle /start command."""
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
    """Handle /help command."""
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
    """Handle SoundCloud URLs."""
    url = message.text.strip()
    
    # Send initial status message
    status_message = await message.answer("🔄 <b>Начинаю загрузку...</b>\nПожалуйста, подождите.")
    
    try:
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            await status_message.edit_text("📥 <b>Загружаю трек с SoundCloud...</b>")
            
            # Download the track
            filepath, info = await downloader.download_track(url, temp_dir)
            
            # Verify file exists
            if not os.path.exists(filepath):
                await status_message.edit_text("❌ <b>Ошибка:</b> Не удалось загрузить файл.")
                return
            
            # Check file size
            file_size = os.path.getsize(filepath)
            
            if file_size > 50 * 1024 * 1024:  # 50MB limit
                await status_message.edit_text(
                    "❌ <b>Ошибка:</b> Файл слишком большой для отправки через Telegram (>50MB)."
                )
                return
            
            if file_size == 0:
                await status_message.edit_text(
                    "❌ <b>Ошибка:</b> Загруженный файл пуст."
                )
                return
            
            await status_message.edit_text("📤 <b>Отправляю аудиофайл...</b>")
            
            # Read file data
            with open(filepath, 'rb') as audio_file:
                audio_data = audio_file.read()
            
            # Extract metadata
            title = info.get('title', 'Неизвестный трек')
            uploader = info.get('uploader', 'Неизвестный исполнитель')
            duration = info.get('duration', 0)
            
            # Format duration
            if duration and isinstance(duration, (int, float)):
                duration = int(duration)
                minutes = duration // 60
                seconds = duration % 60
                duration_str = f"{minutes:02d}:{seconds:02d}"
            else:
                duration_str = "Неизвестно"
                duration = None
            
            # Create audio file object
            audio_file_obj = BufferedInputFile(
                audio_data,
                filename=f"{downloader.sanitize_filename(title)}.mp3"
            )
            
            # Prepare caption
            caption = f"""
🎵 <b>{title}</b>
👤 <b>Исполнитель:</b> {uploader}
⏱ <b>Длительность:</b> {duration_str}
💾 <b>Размер:</b> {file_size / (1024*1024):.1f} MB

<i>Загружено с SoundCloud</i>
            """.strip()
            
            # Send audio file
            await message.answer_audio(
                audio=audio_file_obj,
                caption=caption,
                title=title,
                performer=uploader,
                duration=duration if duration else None
            )
            
            # Delete status message
            await status_message.delete()
            
    except yt_dlp.DownloadError as e:
        logger.error(f"yt-dlp download error: {e}")
        error_message = str(e).lower()
        
        if "private" in error_message or "not available" in error_message:
            await status_message.edit_text(
                "❌ <b>Ошибка доступа к треку</b>\n\n"
                "Возможные причины:\n"
                "• Трек является приватным\n"
                "• Трек недоступен в вашем регионе\n"
                "• Трек был удален автором\n\n"
                "Попробуйте другую ссылку."
            )
        else:
            await status_message.edit_text(
                "❌ <b>Ошибка загрузки с SoundCloud</b>\n\n"
                "Возможные причины:\n"
                "• Проблемы с доступом к SoundCloud\n"
                "• Временные технические неполадки\n"
                "• Неподдерживаемый формат трека\n\n"
                "Попробуйте еще раз через несколько минут."
            )
            
    except FileNotFoundError:
        logger.error("Downloaded file not found")
        await status_message.edit_text(
            "❌ <b>Ошибка:</b> Загруженный файл не найден.\n"
            "Попробуйте еще раз."
        )
        
    except asyncio.TimeoutError:
        logger.error("Download timeout")
        await status_message.edit_text(
            "❌ <b>Таймаут загрузки</b>\n\n"
            "Загрузка заняла слишком много времени.\n"
            "Попробуйте еще раз или выберите другой трек."
        )
        
    except Exception as e:
        logger.error(f"Unexpected error during track download: {e}")
        await status_message.edit_text(
            "❌ <b>Произошла неожиданная ошибка</b>\n\n"
            "Возможные причины:\n"
            "• Временные проблемы с сервисом\n"
            "• Проблемы с интернет-соединением\n"
            "• Неподдерживаемый формат трека\n\n"
            "Попробуйте еще раз через несколько минут."
        )

@dp.message(F.text)
async def text_handler(message: Message):
    """Handle regular text messages."""
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