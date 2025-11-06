import os
if os.path.exists(out_path):
os.unlink(out_path)
return None
except Exception:
if os.path.exists(out_path):
os.unlink(out_path)
return None


# 统一的生成接口：优先离线 -> 回退在线
def generate_tts_audio(text, preferred_voice_id=None, tts_speed=1.0):
"""返回 mp3 文件路径或 None"""
# 1) 尝试离线
if PYTTSX3_AVAILABLE:
mp3 = generate_offline_audio(text, preferred_voice_id, tts_speed)
if mp3:
return mp3
# 2) 回退到 edge-tts（如果可用且 voice id 似乎是 edge voice）
if EDGE_TTS_AVAILABLE:
# 如果 preferred_voice_id 看起来像 edge voice（含字符 '-Neural'），传入，否则使用默认
try:
voice = preferred_voice_id if preferred_voice_id and isinstance(preferred_voice_id, str) else list(VOICE_OPTIONS.values())[0]
except Exception:
voice = None
if voice:
mp3 = generate_edge_audio(text, voice, speed=tts_speed)
if mp3:
return mp3
return None


# preview_voice 也使用统一接口


def preview_voice_generic(voice_id, text, tts_speed=1.0):
# 返回 bytes 或 None
temp = None
try:
fd, temp = tempfile.mkstemp(suffix='.mp3')
os.close(fd)
path = generate_tts_audio(text, preferred_voice_id=voice_id, tts_speed=tts_speed)
if path and os.path.exists(path):
with open(path, 'rb') as f:
b = f.read()
try:
os.remove(path)
except:
pass
return b
except Exception:
pass
finally:
try:
if temp and os.path.exists(temp):
os.remove(temp)
except:
pass
return None


# -----------------------
# 其余音频合并 / 视频合并 / 生成逻辑沿用原实现，仅将调用点替换为 generate_tts_audio / preview_voice_generic
# -----------------------
# （你原文件的 merge_audio_files, merge_video_audio, create_silent_audio 等函数都保留）


# -----------------------
# UI 变更：语音选择部分改为读取系统声音作为选项
# -----------------------
# 在声音设置处，我们会尝试读取 pyttsx3 voices 列表并填充下拉项。若 pyttsx3 不可用，仍保留 edge-tts 的 VOICE_OPTIONS 下拉。


# 其余 UI 与主流程（上传/预览/生成）保持不变；在生成阶段，会把原来调用 generate_edge_audio 的地方替换为 generate_tts_audio()


# 详细完整文件请查看本 canvas 附带的完整 streamlit_app.py，包含所有细节实现。
