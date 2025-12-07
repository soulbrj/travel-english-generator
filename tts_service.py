"""
简化版TTS服务模块
"""

import os
from pathlib import Path
import time

class SimpleTTSService:
    """简化版TTS服务（模拟）"""
    
    def __init__(self, output_dir="output_videos/audio"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
    
    def generate(self, text, voice_type="female_en", rate="-20%", filename=None):
        """模拟生成TTS音频"""
        if not filename:
            timestamp = int(time.time() * 1000)
            filename = f"tts_{timestamp}.mp3"
        
        output_file = self.output_dir / filename
        
        # 模拟生成音频文件
        with open(output_file, 'w') as f:
            f.write(f"模拟音频文件 - {text}\n")
            f.write(f"语音类型: {voice_type}\n")
            f.write(f"语速: {rate}\n")
            f.write(f"生成时间: {time.time()}\n")
        
        # 估算时长（按每字符300ms计算）
        duration = min(len(text) * 300, 5000)
        
        return output_file, duration
    
    def generate_silent(self, duration_ms, output_file=None):
        """生成静默音频"""
        if not output_file:
            timestamp = int(time.time() * 1000)
            output_file = self.output_dir / f"silent_{timestamp}.mp3"
        
        with open(output_file, 'w') as f:
            f.write(f"静默音频 - {duration_ms}ms\n")
        
        return output_file
    
    def get_duration(self, audio_file):
        """获取音频时长"""
        # 模拟：返回固定时长
        return 2000

# 全局实例
tts_service = SimpleTTSService()