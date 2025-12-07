"""
配置文件 - 旅游英语视频生成器
"""

import os
from pathlib import Path

# 基础路径配置
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output_videos"
AUDIO_DIR = OUTPUT_DIR / "audio"
TEMP_DIR = OUTPUT_DIR / "temp"

# 创建必要目录
for directory in [OUTPUT_DIR, AUDIO_DIR, TEMP_DIR]:
    directory.mkdir(exist_ok=True, parents=True)

# 视频生成配置
class VideoConfig:
    """视频生成配置"""
    # 分辨率选项
    RESOLUTIONS = {
        "1920x1080 (全高清)": (1920, 1080),
        "1280x720 (高清)": (1280, 720),
        "854x480 (标清)": (854, 480)
    }
    
    # 帧率选项
    FPS_OPTIONS = [24, 25, 30, 48, 60]
    DEFAULT_FPS = 24
    
    # 比特率选项 (视频)
    VIDEO_BITRATES = ["1M", "2M", "5M", "8M", "10M"]
    DEFAULT_VIDEO_BITRATE = "5M"
    
    # 比特率选项 (音频)
    AUDIO_BITRATES = ["64k", "128k", "192k", "256k", "320k"]
    DEFAULT_AUDIO_BITRATE = "192k"

# 音频配置
class AudioConfig:
    """音频生成配置"""
    # TTS语音配置
    VOICE_CONFIG = {
        'male_en': 'en-US-ChristopherNeural',
        'female_en': 'en-US-JennyNeural',
        'female_cn': 'zh-CN-XiaoxiaoNeural',
        'male_cn': 'zh-CN-YunyangNeural'
    }
    
    # 音频模式
    AUDIO_MODES = {
        "完整模式 (5遍)": {
            "description": "每组句子包含5个朗读版本",
            "steps": [
                {"voice": "female_en", "text_type": "english", "speed": "-20%"},
                {"voice": "male_en", "text_type": "english", "speed": "-20%"},
                {"voice": "female_en", "text_type": "english", "speed": "-20%"},
                {"voice": "male_cn", "text_type": "chinese", "speed": "0%"},
                {"voice": "male_en", "text_type": "english", "speed": "-20%"}
            ]
        },
        "标准模式 (3遍)": {
            "description": "每组句子包含3个朗读版本",
            "steps": [
                {"voice": "female_en", "text_type": "english", "speed": "-20%"},
                {"voice": "male_cn", "text_type": "chinese", "speed": "0%"},
                {"voice": "male_en", "text_type": "english", "speed": "-20%"}
            ]
        },
        "快速模式 (2遍)": {
            "description": "每组句子包含2个朗读版本",
            "steps": [
                {"voice": "female_en", "text_type": "english", "speed": "-10%"},
                {"voice": "male_cn", "text_type": "chinese", "speed": "0%"}
            ]
        }
    }
    
    # 静默配置
    SILENCE_DURATION = 800  # 毫秒
    FADE_DURATION = 50  # 毫秒

# 字幕配置
class SubtitleConfig:
    """字幕显示配置"""
    # 颜色配置 (RGB)
    COLORS = {
        "english": (255, 255, 255),      # 白色
        "chinese": (0, 255, 255),        # 青色
        "phonetic": (255, 255, 0),       # 黄色
        "background": (0, 0, 0),         # 黑色
        "highlight": (255, 105, 180)     # 粉色
    }
    
    # 字体配置
    FONT_SIZES = {
        "large": 48,
        "medium": 36,
        "small": 24
    }
    
    DEFAULT_FONT_SIZE = 36
    
    # 位置配置 (相对位置，0-1之间)
    POSITIONS = {
        "english": 0.35,
        "phonetic": 0.45,
        "chinese": 0.55
    }

# UI配置
class UIConfig:
    """用户界面配置"""
    # 页面标题
    PAGE_TITLE = "旅游英语视频课件生成器"
    PAGE_ICON = "🎬"
    
    # 主题颜色
    PRIMARY_COLOR = "#3B82F6"
    SECONDARY_COLOR = "#10B981"
    ACCENT_COLOR = "#8B5CF6"
    
    # 布局配置
    LAYOUT = "wide"
    INITIAL_SIDEBAR_STATE = "expanded"

# 导出配置
class ExportConfig:
    """导出配置"""
    # 支持的文件格式
    VIDEO_FORMATS = ["mp4", "avi", "mov"]
    AUDIO_FORMATS = ["mp3", "wav", "ogg"]
    SUBTITLE_FORMATS = ["srt", "ass", "vtt"]
    
    # 默认格式
    DEFAULT_VIDEO_FORMAT = "mp4"
    DEFAULT_AUDIO_FORMAT = "mp3"
    DEFAULT_SUBTITLE_FORMAT = "srt"
    
    # 压缩质量 (0-100)
    QUALITY = {
        "high": 90,
        "medium": 75,
        "low": 60
    }

# 应用配置
APP_CONFIG = {
    "video": VideoConfig(),
    "audio": AudioConfig(),
    "subtitle": SubtitleConfig(),
    "ui": UIConfig(),
    "export": ExportConfig()
}