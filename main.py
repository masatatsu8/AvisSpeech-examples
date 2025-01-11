import os
from fastapi import FastAPI, Request, WebSocket
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import openai
from dotenv import load_dotenv
from speech import speech
import json
import asyncio

# 環境変数の読み込み
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()

# 静的ファイルとテンプレートの設定
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    while True:
        try:
            # クライアントからのメッセージを受信
            user_message = await websocket.receive_text()
            
            # GPT-4からの応答を取得
            messages = [
                {"role": "system", "content": "あなたはご主人様に仕えるメイドです。できるだけ簡潔に応答してください。"},
                {"role": "user", "content": user_message}
            ]
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=messages,
                max_tokens=250,
                temperature=0.7,
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # 音声合成を開始
            progress = await speech(ai_response)
            
            # 応答テキストを文字単位で分割
            total_chars = len(ai_response)
            
            # 音声の進行に合わせて文字を送信
            last_char_index = 0
            while not progress.is_finished:
                current_ratio = progress.current_sample / progress.total_samples
                target_char_index = int(current_ratio * total_chars)
                
                if target_char_index > last_char_index:
                    # 新しい文字を送信
                    new_chars = ai_response[last_char_index:target_char_index]
                    await websocket.send_json({
                        "type": "partial",
                        "text": new_chars
                    })
                    last_char_index = target_char_index
                
                await asyncio.sleep(0.01)
            
            # 残りの文字を送信
            if last_char_index < total_chars:
                remaining_chars = ai_response[last_char_index:]
                await websocket.send_json({
                    "type": "partial",
                    "text": remaining_chars
                })
            
            # 完了通知を送信
            await websocket.send_json({
                "type": "complete"
            })
            
        except Exception as e:
            print(f"Error: {e}")
            await websocket.close()
            break

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
