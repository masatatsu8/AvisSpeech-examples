import asyncio
import io
import sys
from speech import speech

    
async def main():
    if not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    else:
        text = ' '.join(sys.argv[1:])
    
    if text:
        thread = await speech(text)
        print(text)
        # オプション: スレッドの終了を待つ場合
        # thread.join()


if __name__ == '__main__':
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
    asyncio.run(main())
