# AvisSpeech examples

## 概要

[AivisSpeech](https://aivis-project.com/#products-aivisspeech)を用いたサンプル実装です。


**Maid Chat**は、生成AI とを組み合わせたメイドキャラクターとの対話システムです。

**avis_speech.py**は、AivisSpeechを使用した音声合成とmacOS通知の統合スクリプトです。コマンドライン、パイプライン、他のPythonアプリケーションから簡単に呼び出すことができ、カスタムアイコン付きの通知機能も提供します。

### 主な機能
- **インタラクティブな対話**: CLI版とWebベースのGUI版
- **高品質音声合成**: AivisSpeechによるリアルタイム音声出力
- **macOS通知統合**: カスタムアイコン対応の視覚的フィードバック
- **柔軟な使用方法**: スタンドアロン実行、パイプライン処理、ライブラリとしての利用


### AivisSpeechのセットアップ
詳細なインストール手順は[AivisSpeech公式GitHub](https://github.com/Aivis-Project/AivisSpeech)をご確認ください。

```bash
# AivisSpeechのクローンとセットアップ
git clone https://github.com/Aivis-Project/AivisSpeech.git
cd AivisSpeech
# セットアップ手順は公式ドキュメントに従ってください
```

## 特徴

- 生成AI API (OpenAI, Ollama, LM Studio)による自然な対話
- リアルタイムな音声合成とmacOS通知
- テキストと音声の同期表示
- メイドキャラクターとしての応答
- 会話履歴の保持による文脈理解
- カスタムアイコン付きmacOS通知システム

## 必要条件

### 基本要件
- **Python 3.8以上**
- **macOS** (通知機能用)
- **AivisSpeech**
- **OpenAI APIキー**

### macOS依存ライブラリ

#### 必須ツール
```bash
# Homebrew (推奨)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# terminal-notifier (アイコン付き通知用)
brew install terminal-notifier

# alerter (オプション、より高度な通知制御)
brew install alerter
```

#### Pythonライブラリ
```bash
# 音声処理用（PortAudioが必要）
brew install portaudio
pip install pyaudio
```

## セットアップ手順

### 1. 前提条件の確認
```bash
# macOSのバージョン確認
sw_vers

# Homebrewがインストールされているか確認
brew --version

# Python 3.8以上がインストールされているか確認
python3 --version
```

### 2. macOS依存ツールのインストール
```bash
# PortAudio (音声処理用)
brew install portaudio

# terminal-notifier (アイコン付き通知用)
brew install terminal-notifier

# alerter (オプション、高度な通知制御)
brew install alerter
```

### 3. プロジェクトのセットアップ
```bash
# リポジトリをクローン
git clone [repository-url]
cd maid-chat

# Python依存パッケージをインストール
pip install -r requirements.txt

# 環境変数の設定
cp env.example .env
# .envファイルを編集してAPIキーを設定
```

### 4. AivisSpeechサーバの準備
```bash
# AivisSpeechサーバーの起動
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
2. ブラウザで`http://localhost:8000`にアクセス

### 音声通知スクリプト (avis_speech.py)
```bash
# 基本的な使用方法（デフォルトは非同期実行）
python3 avis_speech.py "こんにちは、ご主人様"

# 名前付きで通知
python3 avis_speech.py --name "メイド" "お疲れ様でした"

# カスタムアイコンで通知
python3 avis_speech.py --left-icon static/images/maid_icon.png "重要なお知らせです"

# 右側アイコンも表示
python3 avis_speech.py --show-right-icon --icon static/images/maid_icon.png "画像付き通知"

# デバッグモード
python3 avis_speech.py --debug-notify --name "デバッグ" "通知テスト"

# 同期実行（音声再生完了まで待機）
python3 avis_speech.py --sync --name "メイド" "同期再生"

# 標準入力からの入力
echo "パイプからの入力です" | python3 avis_speech.py --name "パイプ"
```

#### 実行モードについて

**avis_speech.py**は、用途に応じて2つの実行モードを選択できます。

##### 非同期実行（デフォルト）
```bash
# 音声合成を開始後、すぐにコマンドラインに戻る
python3 avis_speech.py "バックグラウンド再生"

# 複数の音声を連続で開始
python3 avis_speech.py "最初のメッセージ"
python3 avis_speech.py "2番目のメッセージ"
python3 avis_speech.py "3番目のメッセージ"
```

##### 同期実行
```bash
# 音声再生完了まで待機してから終了
python3 avis_speech.py --sync "音声再生完了まで待機"

# スクリプトで順次実行したい場合
python3 avis_speech.py --sync "1つ目"
python3 avis_speech.py --sync "2つ目"  # 1つ目の完了後に実行
```

#### 通知オプション

| オプション | 説明 |
|----------|------|
| `--name` | 通知に表示する名前 |
| `--left-icon` | 左側アイコン（appIcon）のパス |
| `--show-right-icon` | 右側アイコン（contentImage）を表示 |
| `--icon`, `--right-icon` | 右側アイコンのパス |
| `--sender` | 送信元アプリのBundle ID |
| `--prefer-alerter` | alerterを優先使用 |
| `--no-notify` | 通知を無効化（音声のみ） |
| `--debug-notify` | デバッグ出力を有効化 |
| `--sync` | 同期実行（音声再生完了まで待機） |

## 機能の詳細

### 音声合成システム
- **低遅延音声再生**: 128サンプルのバッファサイズ
- **ノイズ軽減**: 10msのフェードイン処理
- **非同期処理**: 音声と文字表示の同期
- **品質最適化**: ハードウェア性能に応じた自動調整

### macOS通知システム
- **3段階フォールバック**: alerter → terminal-notifier → AppleScript
- **カスタムアイコン対応**: 左右独立したアイコン設定
- **ターミナルアイコン回避**: 自動sender設定でターミナルアイコンを非表示
- **透明アイコン機能**: 左側アイコンの完全非表示
- **デバッグ機能**: 実行コマンドと結果の詳細出力

### 対話システム
- **文脈保持**: 会話履歴の保持（最新4往復）
- **キャラクター設定**: メイドキャラクターとしての一貫した応答
- **非同期処理**: 円滑な対話のための並行処理

## トラブルシューティング

### 通知が表示されない場合
```bash
# terminal-notifierの確認
which terminal-notifier
terminal-notifier --version

# 手動でパス指定
python3 avis_speech.py --terminal-notifier /opt/homebrew/bin/terminal-notifier "テスト"

# alerterを試す
python3 avis_speech.py --prefer-alerter "テスト"
```

### 音声が再生されない場合
```bash
# PortAudioの確認
brew list portaudio

# PyAudioの再インストール
pip uninstall pyaudio
pip install pyaudio
```

### アイコンが表示されない場合
```bash
# ファイルパスの確認
ls -la static/images/maid_icon.png

# 絶対パスで指定
python3 avis_speech.py --left-icon "$(pwd)/static/images/maid_icon.png" "テスト"
```

## 注意事項

- **ライセンス**: AivisSpeechのライセンスについては[公式GitHub](https://github.com/Aivis-Project/AivisSpeech)をご確認ください
- **API料金**: OpenAI APIの利用料金が発生します
- **パフォーマンス**: 音声合成の品質はハードウェア性能に依存します
- **プライバシー**: 通知内容は他のユーザーからも見える場合があります
- **macOS専用**: 通知機能はmacOSでのみ動作します