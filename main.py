import os
from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from openai import AsyncOpenAI
from dotenv import load_dotenv
from speech import speech
import json
import asyncio
from database import database, Chat, ChatMessage
from datetime import datetime
import pytz
from pydantic import BaseModel

# 環境変数の読み込み
load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

# 静的ファイルとテンプレートの設定
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# タイムゾーンの設定
jst = pytz.timezone('Asia/Tokyo')

def convert_to_jst(dt):
    """UTCをJSTに変換する"""
    if dt.tzinfo is None:  # タイムゾーン情報がない場合はUTCとして扱う
        dt = pytz.utc.localize(dt)
    return dt.astimezone(jst)

class ChatTitleUpdate(BaseModel):
    title: str


@app.on_event("startup")
async def startup():
    await database.connect()


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # チャット一覧を取得
    query = Chat.__table__.select().order_by(Chat.updated_at.desc())
    chats = await database.fetch_all(query)
    
    # 日時をJSTに変換
    converted_chats = []
    for chat in chats:
        chat_dict = dict(chat)
        chat_dict['created_at'] = convert_to_jst(chat_dict['created_at'])
        chat_dict['updated_at'] = convert_to_jst(chat_dict['updated_at'])
        converted_chats.append(chat_dict)
    
    return templates.TemplateResponse(
        "chat_list.html", {"request": request, "chats": converted_chats}
    )


@app.post("/chat/new")
async def create_chat():
    # 新しいチャットを作成
    query = Chat.__table__.insert().values(
        title="新しい会話", created_at=datetime.utcnow(), updated_at=datetime.utcnow()
    )
    chat_id = await database.execute(query)
    return RedirectResponse(url=f"/chat/{chat_id}", status_code=303)


@app.get("/chat/{chat_id}", response_class=HTMLResponse)
async def read_chat(request: Request, chat_id: int):
    # チャット一覧を取得
    chats_query = Chat.__table__.select().order_by(Chat.updated_at.desc())
    chats = await database.fetch_all(chats_query)
    
    # 日時をJSTに変換
    converted_chats = []
    for chat in chats:
        chat_dict = dict(chat)
        chat_dict['created_at'] = convert_to_jst(chat_dict['created_at'])
        chat_dict['updated_at'] = convert_to_jst(chat_dict['updated_at'])
        converted_chats.append(chat_dict)
    
    # 現在のチャットの情報を取得
    chat_query = Chat.__table__.select().where(Chat.id == chat_id)
    chat = await database.fetch_one(chat_query)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # 現在のチャットの日時をJSTに変換
    chat_dict = dict(chat)
    chat_dict['created_at'] = convert_to_jst(chat_dict['created_at'])
    chat_dict['updated_at'] = convert_to_jst(chat_dict['updated_at'])
    
    # チャットのメッセージを取得
    messages_query = (
        ChatMessage.__table__.select()
        .where(ChatMessage.chat_id == chat_id)
        .order_by(ChatMessage.timestamp)
    )
    messages = await database.fetch_all(messages_query)
    
    # メッセージの日時をJSTに変換
    converted_messages = []
    for message in messages:
        message_dict = dict(message)
        message_dict['timestamp'] = convert_to_jst(message_dict['timestamp'])
        converted_messages.append(message_dict)
    
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "chat": chat_dict,
            "messages": converted_messages,
            "chats": converted_chats,
        },
    )


@app.put("/chat/{chat_id}/title")
async def update_chat_title(chat_id: int, title_update: ChatTitleUpdate):
    query = (
        Chat.__table__.update()
        .where(Chat.id == chat_id)
        .values(title=title_update.title, updated_at=datetime.utcnow())
    )
    await database.execute(query)
    return {"status": "success"}


@app.websocket("/ws/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: int):
    await websocket.accept()

    while True:
        try:
            # クライアントからのメッセージを受信
            user_message = await websocket.receive_text()

            # ユーザーメッセージをデータベースに保存
            query = ChatMessage.__table__.insert().values(
                chat_id=chat_id,
                role="user",
                content=user_message,
                timestamp=datetime.utcnow(),
            )
            await database.execute(query)

            # チャットの更新日時を更新
            update_query = (
                Chat.__table__.update()
                .where(Chat.id == chat_id)
                .values(updated_at=datetime.utcnow())
            )
            await database.execute(update_query)

            # GPT-4からの応答を取得
            messages = [
                {
                    "role": "system",
                    "content": "あなたはご主人様に仕えるメイドです。できるだけ簡潔に応答してください。",
                },
                {"role": "user", "content": user_message},
            ]

            response = await client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=250,
                temperature=0.7,
            )

            ai_response = response.choices[0].message.content.strip()

            # アシスタントの応答をデータベースに保存
            query = ChatMessage.__table__.insert().values(
                chat_id=chat_id,
                role="assistant",
                content=ai_response,
                timestamp=datetime.utcnow(),
            )
            await database.execute(query)

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
                    await websocket.send_json({"type": "partial", "text": new_chars})
                    last_char_index = target_char_index

                await asyncio.sleep(0.01)

            # 残りの文字を送信
            if last_char_index < total_chars:
                remaining_chars = ai_response[last_char_index:]
                await websocket.send_json({"type": "partial", "text": remaining_chars})

            # 完了通知を送信
            await websocket.send_json({"type": "complete"})

        except Exception as e:
            print(f"Error: {e}")
            await websocket.close()
            break


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
