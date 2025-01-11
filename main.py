import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from openai import AsyncOpenAI
from speech import speech
import json
import asyncio
from database import database, Chat, ChatMessage
from datetime import datetime
import pytz
import aiohttp
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect

# 環境変数の読み込み
load_dotenv()

# エンジンの設定を読み込み
ENGINE = os.getenv("ENGINE", "openai")  # openai, ollama, deepseek
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "7shi/tanuki-dpo-v1.0:8b-q6_K")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

app = FastAPI()

# 静的ファイルとテンプレートの設定
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# タイムゾーンの設定
jst = pytz.timezone("Asia/Tokyo")


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
        chat_dict["created_at"] = convert_to_jst(chat_dict["created_at"])
        chat_dict["updated_at"] = convert_to_jst(chat_dict["updated_at"])
        converted_chats.append(chat_dict)

    return templates.TemplateResponse(
        "chat_list.html", {"request": request, "chats": converted_chats}
    )


@app.post("/chat/new")
async def create_chat():
    """新しいチャットを作成する"""
    query = Chat.__table__.insert().values(
        title="新しい会話",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    chat_id = await database.execute(query)
    return {"chat_id": chat_id}


@app.get("/chat/{chat_id}", response_class=HTMLResponse)
async def read_chat(request: Request, chat_id: int):
    # チャット一覧を取得
    chats_query = Chat.__table__.select().order_by(Chat.updated_at.desc())
    chats = await database.fetch_all(chats_query)

    # 日時をJSTに変換
    converted_chats = []
    for chat in chats:
        chat_dict = dict(chat)
        chat_dict["created_at"] = convert_to_jst(chat_dict["created_at"])
        chat_dict["updated_at"] = convert_to_jst(chat_dict["updated_at"])
        converted_chats.append(chat_dict)

    # 現在のチャットの情報を取得
    chat_query = Chat.__table__.select().where(Chat.id == chat_id)
    chat = await database.fetch_one(chat_query)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # 現在のチャットの日時をJSTに変換
    chat_dict = dict(chat)
    chat_dict["created_at"] = convert_to_jst(chat_dict["created_at"])
    chat_dict["updated_at"] = convert_to_jst(chat_dict["updated_at"])

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
        message_dict["timestamp"] = convert_to_jst(message_dict["timestamp"])
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


@app.delete("/chats/{chat_id}")
async def delete_chat(chat_id: int):
    """チャットを削除する"""
    # メッセージを削除
    delete_messages_query = ChatMessage.__table__.delete().where(
        ChatMessage.chat_id == chat_id
    )
    await database.execute(delete_messages_query)

    # チャットを削除
    delete_chat_query = Chat.__table__.delete().where(Chat.id == chat_id)
    await database.execute(delete_chat_query)

    # 直近の会話を取得
    query = Chat.__table__.select().order_by(Chat.updated_at.desc())
    latest_chat = await database.fetch_one(query)
    
    return {"status": "success", "next_chat_id": latest_chat.id if latest_chat else None}


@app.delete("/messages/{message_id}")
async def delete_message(message_id: int):
    """メッセージを削除する"""
    # メッセージを削除
    delete_query = ChatMessage.__table__.delete().where(
        ChatMessage.id == message_id
    )
    await database.execute(delete_query)
    return {"status": "success"}


async def get_openai_response(messages):
    """OpenAI APIからの応答をストリーミングで取得"""
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    async for chunk in await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        max_tokens=250,
        temperature=0.7,
        stream=True,
    ):
        if chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content


async def get_ollama_response(messages):
    """Ollama APIからの応答をストリーミングで取得"""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 250,
                },
            },
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Ollama API error: {error_text}")

            async for line in response.content:
                if not line:
                    continue
                try:
                    line_text = line.decode("utf-8")
                    json_line = json.loads(line_text)
                    if "error" in json_line:
                        raise Exception(f"Ollama API error: {json_line['error']}")
                    if "done" in json_line and json_line["done"]:
                        break
                    if "message" in json_line and "content" in json_line["message"]:
                        chunk = json_line["message"]["content"]
                        yield chunk
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    raise


async def get_deepseek_response(messages):
    """DeepSeek APIからの応答をストリーミングで取得"""
    client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    async for chunk in await client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=messages,
        max_tokens=250,
        temperature=0.7,
        stream=True,
    ):
        if chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content


async def split_into_sentences(text):
    """テキストを文単位で分割"""
    # 句点や感嘆符などで分割
    delimiters = ["。", "！", "？", "!", "?"]
    sentences = []
    current = ""

    for char in text:
        current += char
        if any(char == d for d in delimiters):
            if current.strip():
                sentences.append(current)
            current = ""

    if current.strip():
        sentences.append(current)

    return sentences


async def display_with_speech(websocket, text, progress):
    """音声の進行に合わせて文字を表示"""
    total_chars = len(text)
    last_char_index = 0

    while not progress.is_finished:
        current_ratio = progress.current_sample / progress.total_samples
        target_char_index = int(current_ratio * total_chars)

        if target_char_index > last_char_index:
            # 新しい文字を送信
            new_chars = text[last_char_index:target_char_index]
            await websocket.send_json({"type": "partial", "text": new_chars})
            last_char_index = target_char_index

        await asyncio.sleep(0.01)

    # 残りの文字を送信
    if last_char_index < total_chars:
        remaining_chars = text[last_char_index:]
        await websocket.send_json({"type": "partial", "text": remaining_chars})


async def get_chat_history(chat_id):
    """チャットの履歴を取得する"""
    messages_query = (
        ChatMessage.__table__.select()
        .where(ChatMessage.chat_id == chat_id)
        .order_by(ChatMessage.timestamp)
    )
    messages = await database.fetch_all(messages_query)
    return [{"role": msg["role"], "content": msg["content"]} for msg in messages]


async def process_streaming_response(websocket, response_generator):
    """ストリーミング応答を処理し、音声合成と表示を行う"""
    full_response = ""
    current_sentence = ""
    current_progress = None

    try:
        async for chunk in response_generator:
            full_response += chunk
            current_sentence += chunk

            # 文の終わりを検出
            if any(current_sentence.endswith(d) for d in ["。", "！", "？", "!", "?"]):
                if current_progress is not None:
                    # 前の音声が終わるのを待つ
                    while not current_progress.is_finished:
                        await asyncio.sleep(0.01)

                # 新しい文の音声合成を開始
                current_progress = await speech(current_sentence)
                await display_with_speech(websocket, current_sentence, current_progress)
                current_sentence = ""

    except Exception as e:
        raise

    # 残りの文を処理
    if current_sentence.strip():
        if current_progress is not None:
            while not current_progress.is_finished:
                await asyncio.sleep(0.01)
        current_progress = await speech(current_sentence)
        await display_with_speech(websocket, current_sentence, current_progress)

    return full_response


@app.websocket("/ws/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: int):
    await websocket.accept()

    try:
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

                # チャット履歴を取得
                history = await get_chat_history(chat_id)

                # LLMへのメッセージを構築
                messages = [
                    {
                        "role": "system",
                        "content": "あなたはご主人様に仕えるメイドです。できるだけ簡潔に応答してください。これまでの会話履歴を考慮して応答してください。",
                    },
                ]
                # 履歴を追加（最新の10件まで）
                messages.extend(history[-10:])

                # エンジンに応じたレスポンスジェネレータを選択
                if ENGINE == "openai":
                    response_generator = get_openai_response(messages)
                elif ENGINE == "deepseek":
                    response_generator = get_deepseek_response(messages)
                else:  # ollama
                    response_generator = get_ollama_response(messages)

                # 応答を処理
                full_response = await process_streaming_response(
                    websocket, response_generator
                )

                # 余分なメッセージを削除（Ollama用）
                if ENGINE == "ollama" and "banphrase" in full_response:
                    full_response = full_response.split("banphrase")[0].strip()

                # アシスタントの応答をデータベースに保存
                query = ChatMessage.__table__.insert().values(
                    chat_id=chat_id,
                    role="assistant",
                    content=full_response,
                    timestamp=datetime.utcnow(),
                )
                await database.execute(query)

                # 完了通知を送信
                await websocket.send_json({"type": "complete"})

            except WebSocketDisconnect:
                print("WebSocket disconnected")
                break
            except Exception as e:
                print(f"Error in websocket loop: {e}")
                try:
                    await websocket.send_json({
                        "type": "error",
                        "content": str(e)
                    })
                except:
                    pass
                break

    except Exception as e:
        print(f"Websocket error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
