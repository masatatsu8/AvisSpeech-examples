import os
import sys
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv
from speech import speech  # 音声合成用の関数をインポート
import time
import requests

# 環境変数を読み込む
load_dotenv()

# ENGINE設定を読み込み
ENGINE = os.getenv("ENGINE", "openai").strip()

# エンジンに応じてクライアントを初期化
if ENGINE == "openai":
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    if not OPENAI_API_KEY:
        print("エラー: OPENAI_API_KEYが設定されていません")
        sys.exit(1)
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
elif ENGINE == "ollama":
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").strip()
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi4:latest").strip()
elif ENGINE == "lm_studio":
    LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234").strip()
    LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "openai/gpt-oss-20b").strip()
    # LM StudioはOpenAI互換APIなのでAsyncOpenAIクライアントを使用
    client = AsyncOpenAI(base_url=f"{LM_STUDIO_URL}/v1", api_key="lm-studio")
else:
    print(f"エラー: 未対応のエンジン '{ENGINE}' が指定されています")
    sys.exit(1)

print(f"使用エンジン: {ENGINE}")
if ENGINE == "openai":
    print(f"OpenAIモデル: {OPENAI_MODEL}")
elif ENGINE == "ollama":
    print(f"Ollamaモデル: {OLLAMA_MODEL}")
elif ENGINE == "lm_studio":
    print(f"LM Studioモデル: {LM_STUDIO_MODEL}")

# 音声の進行状況に合わせて文字を表示する
async def display_text_with_audio_progress(text, progress):
    """音声の進行状況に合わせて文字を表示する"""
    sys.stdout.write("\rメイド: ")
    sys.stdout.flush()
    
    text_length = len(text)
    last_char_index = 0
    
    while not progress.is_finished:
        # 音声の進行状況に基づいて、次に表示する文字のインデックスを計算
        current_ratio = progress.current_sample / progress.total_samples
        target_char_index = int(current_ratio * text_length)
        
        # 新しい文字を表示
        while last_char_index < target_char_index and last_char_index < text_length:
            sys.stdout.write(text[last_char_index])
            sys.stdout.flush()
            last_char_index += 1
        
        await asyncio.sleep(0.01)  # 短い待機時間
    
    # 残りの文字を表示
    while last_char_index < text_length:
        sys.stdout.write(text[last_char_index])
        sys.stdout.flush()
        last_char_index += 1
    
    sys.stdout.write("\n")
    sys.stdout.flush()

async def get_openai_response(messages):
    """OpenAI APIからの応答を取得"""
    try:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=250,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI APIエラー: {e}")
        return "申し訳ありません。エラーが発生しました。"

async def get_lm_studio_response(messages):
    """LM Studio APIからの応答を取得"""
    try:
        response = await client.chat.completions.create(
            model=LM_STUDIO_MODEL,
            messages=messages,
            max_tokens=250,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LM Studio APIエラー: {e}")
        return "申し訳ありません。エラーが発生しました。"

async def get_ollama_response(messages):
    """Ollama APIからの応答を取得"""
    try:
        # Ollamaの形式に変換
        ollama_messages = []
        for msg in messages:
            ollama_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        data = {
            "model": OLLAMA_MODEL,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 250
            }
        }
        
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result["message"]["content"].strip()
        else:
            print(f"Ollama APIエラー: {response.status_code}")
            return "申し訳ありません。エラーが発生しました。"
    except requests.exceptions.RequestException as e:
        print(f"Ollama接続エラー: {e}")
        return "申し訳ありません。Ollamaサーバーに接続できませんでした。"
    except Exception as e:
        print(f"Ollamaエラー: {e}")
        return "申し訳ありません。エラーが発生しました。"

async def get_ai_response(prompt, conversation_history=None):
    if conversation_history is None:
        conversation_history = []
    
    # 会話履歴を含めてメッセージを構築
    messages = [
        {"role": "system",
        "content": "あなたはご主人様に仕えるメイドです。できるだけ簡潔に応答してください。"},
    ]
    
    # 会話履歴を追加
    messages.extend(conversation_history)
    
    # 新しいプロンプトを追加
    messages.append({"role": "user", "content": prompt})
    
    # エンジンに応じて応答を取得
    if ENGINE == "openai":
        return await get_openai_response(messages)
    elif ENGINE == "ollama":
        return await get_ollama_response(messages)
    elif ENGINE == "lm_studio":
        return await get_lm_studio_response(messages)
    else:
        return "申し訳ありません。未対応のエンジンです。"

async def interactive_chat():
    conversation_history = []
    print("対話を開始します。終了するには 'quit' と入力してください。")
    
    while True:
        try:
            # ユーザー入力を待機
            user_input = input("\nあなた: ").strip()
            
            if user_input.lower() in ['quit', 'exit', '終了']:
                print("対話を終了します。")
                break
            
            if not user_input:
                continue
            
            # 会話履歴に追加
            conversation_history.append({"role": "user", "content": user_input})
            
            # AI の応答を取得
            ai_response = await get_ai_response(user_input, conversation_history)
            
            # 会話履歴に追加
            conversation_history.append({"role": "assistant", "content": ai_response})
            
            # 音声合成を開始し、進行状況オブジェクトを取得
            progress = await speech(ai_response)
            
            # 音声再生の進行に合わせて文字を表示
            await display_text_with_audio_progress(ai_response, progress)
            
            # 会話履歴を最新の4往復に制限
            if len(conversation_history) > 8:
                conversation_history = conversation_history[-8:]
                
        except KeyboardInterrupt:
            print("\n対話を終了します。")
            break
        except Exception as e:
            print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(interactive_chat())
    except KeyboardInterrupt:
        print("\n終了します。")
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
