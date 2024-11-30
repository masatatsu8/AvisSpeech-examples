import os
import sys
import asyncio
import openai
from dotenv import load_dotenv
from speech import speech  # 音声合成用の関数をインポート

# 環境変数から OpenAI API キーを読み込む
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

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
    
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=250,  # 応答の長さを制限
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error getting AI response: {e}")
        return "申し訳ありません。エラーが発生しました。"

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
            print(f"メイド: {ai_response}")
            
            # 会話履歴に追加
            conversation_history.append({"role": "assistant", "content": ai_response})
            
            # 音声合成で応答を読み上げ
            await speech(ai_response)
            
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
