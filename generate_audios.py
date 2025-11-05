import edge_tts
import asyncio
import pandas as pd
import os

EXCEL_FILE = "example/sentences.xlsx"  # 你的 Excel 文件路径
OUTPUT_DIR = "example/audios"

voices = {
    "英文男声": "en-US-GuyNeural",
    "英文女声": "en-US-JennyNeural",
    "中文音色": "zh-CN-XiaoxiaoNeural"
}

segment_order = [
    ("英文男声", "english"),
    ("英文女声", "english"),
    ("中文音色", "chinese"),
    ("英文男声", "english")
]

async def gen_tts(text, voice, path):
    if not text or str(text).strip().lower() == "nan":
        return
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(path)
    print(f"✅ 已生成: {path}")

async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df = pd.read_excel(EXCEL_FILE)

    for i, row in df.iterrows():
        eng = str(row.get("英语", "")).strip()
        chn = str(row.get("中文", "")).strip()

        for j, (voice_label, lang_type) in enumerate(segment_order, start=1):
            voice = voices[voice_label]
            text = eng if lang_type == "english" else chn
            filename = f"{i+1}-{j}.mp3"
            out_path = os.path.join(OUTPUT_DIR, filename)
            await gen_tts(text, voice, out_path)

    print("\n🎉 所有音频生成完毕！")
    print(f"文件保存在: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    asyncio.run(main())
