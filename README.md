# AI Maid Chat

音声合成を使用したメイドキャラクターとの対話システム。OpenAI GPT-4と[AivisSpeech](https://aivis-project.com/#products-aivisspeech)を組み合わせて、テキストと音声による自然な対話を実現します。

## 特徴

- GPT-4を使用した自然な対話
- リアルタイムな音声合成
- テキストと音声の同期表示
- メイドキャラクターとしての応答
- 会話履歴の保持による文脈理解

## 必要条件

- Python 3.8以上
- AivisSpeech
- OpenAI APIキー

## 依存パッケージ

```
openai
python-dotenv
requests
pyaudio
numpy
```

## セットアップ

1. リポジトリをクローン
```bash
git clone [repository-url]
cd maid-chat
```

2. 依存パッケージをインストール
```bash
pip install -r requirements.txt
```

3. 環境変数の設定
`.env.example`をコピーして`.env`を作成し、各APIに関する設定を記述。
```bash
cp env.example .env
# .envファイルを編集してAPIキーを設定
```

4. AivisSpeechサーバーの起動
```bash
./run_server.sh
```

## 使用方法

### CLI版
1. プログラムを起動
```bash
python cli.py
```
2. プロンプトに従って対話を入力
3. 'quit'または'終了'と入力して終了

### GUI版
1. プログラムを起動
```bash
uvicorn main:app --reload --port 8000
```
2. ブラヴザで`http://localhost:8000`にアクセス



## 機能の詳細

### 音声合成
- 10msのフェードインによるノイズ軽減
- 128サンプルのバッファサイズによる低遅延
- 音声と文字表示の同期

### 対話システム
- 会話履歴の保持（最新4往復）
- メイドキャラクターとしての一貫した応答
- 非同期処理による円滑な対話


## 注意事項

- AivisSpeechのライセンスに従って使用してください
- OpenAI APIの利用料金が発生します
- 音声合成の品質はハードウェア性能に依存します