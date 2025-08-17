import sys
import argparse
import asyncio
import subprocess
import os
import shutil
from typing import Optional, List
from importlib import import_module


def _escape_applescript(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')

def notify_mac(
    message: str,
    title: str = "Avis",
    subtitle: Optional[str] = None,
    icon_path: Optional[str] = None,  # right icon (contentImage)
    left_icon_path: Optional[str] = None,  # left icon (appIcon)
    sender: Optional[str] = None,
    debug: bool = False,
    tn_path: Optional[str] = None,
    prefer_alerter: bool = False,
    alerter_path: Optional[str] = None,
    name: Optional[str] = None,  # 名前指定
    show_right_icon: bool = False,  # 右アイコンをデフォルトで無効
) -> bool:
    """macOS の通知バナーを表示する。
    
    Args:
        message: 通知メッセージ
        title: 通知タイトル
        subtitle: サブタイトル（オプション）
        icon_path: 右側アイコンのパス（contentImage）
        left_icon_path: 左側アイコンのパス（appIcon）
        sender: 送信元アプリのBundle ID
        debug: デバッグ出力の有効化
        tn_path: terminal-notifierの直接パス指定
        prefer_alerter: alerterを優先使用
        alerter_path: alerterの直接パス指定
        name: 通知に表示する名前
        show_right_icon: 右側アイコンの表示を有効化
        
    Returns:
        bool: 通知の送信に成功した場合True（非macOSの場合はFalse）
    """
    if sys.platform != "darwin":
        return False
    def _find_executable(name: str, custom_path: Optional[str] = None) -> Optional[str]:
        """実行可能ファイルを検索する"""
        candidates = []
        if custom_path:
            candidates.append(custom_path)
        
        found = shutil.which(name)
        if found:
            candidates.append(found)
        
        candidates.extend([
            f"/opt/homebrew/bin/{name}",
            f"/usr/local/bin/{name}",
        ])
        
        for candidate in candidates:
            if candidate and os.path.exists(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return None
    
    # 通知ツールの検出
    alerter = _find_executable("alerter", alerter_path) if prefer_alerter else None
    tn = _find_executable("terminal-notifier", tn_path)

    if debug:
        print(f"通知バックエンド検出: alerter={alerter}, terminal-notifier={tn}")
        if icon_path:
            print(f"右アイコン: {os.path.abspath(icon_path)}")
        if left_icon_path:
            print(f"左アイコン: {os.path.abspath(left_icon_path)}")

    def _run_alerter() -> bool:
        """alerterを使用して通知を送信"""
        display_title = f"{name}: {title}" if name else title
        cmd = [alerter, "-title", display_title, "-message", message]
        if subtitle:
            cmd += ["-subtitle", subtitle]
        
        # ターミナルアイコンを回避するためのsender設定
        cmd += ["-sender", "com.apple.Finder"]
        
        # アイコン設定
        if left_icon_path and os.path.exists(left_icon_path):
            cmd += ["-appIcon", os.path.abspath(left_icon_path)]
        elif show_right_icon and icon_path and os.path.exists(icon_path):
            cmd += ["-appIcon", os.path.abspath(icon_path)]
        
        if show_right_icon and icon_path and os.path.exists(icon_path):
            cmd += ["-contentImage", os.path.abspath(icon_path)]
        
        if debug:
            print("alerter コマンド:", " ".join(cmd))
        
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=10)
            if debug:
                print(f"alerter 実行結果: exit={res.returncode}")
            return res.returncode == 0
        except (subprocess.TimeoutExpired, Exception) as e:
            if debug:
                print(f"alerter エラー: {e}")
            return False
    
    # alerterを優先使用（指定時）
    if alerter:
        if _run_alerter():
            return True

    def _run_terminal_notifier() -> bool:
        """terminal-notifierを使用して通知を送信"""
        display_title = f"{name}" if name else title
        cmd = [tn, "-title", display_title, "-message", message]
        if subtitle:
            cmd += ["-subtitle", subtitle]
        
        # ターミナルアイコンを回避するためのsender設定
        cmd += ["-sender", sender or "com.apple.Finder"]
        
        # 右側アイコン
        abs_right = None
        if show_right_icon and icon_path and os.path.exists(icon_path):
            abs_right = os.path.abspath(icon_path)
            cmd += ["-contentImage", abs_right]
        
        # 左側アイコン
        abs_left = None
        if left_icon_path and os.path.exists(left_icon_path):
            abs_left = os.path.abspath(left_icon_path)
        elif show_right_icon and abs_right:
            abs_left = abs_right
        if abs_left:
            cmd += ["-appIcon", abs_left]
        
        if debug:
            print("terminal-notifier コマンド:", " ".join(cmd))
        
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=10)
            if debug:
                print(f"terminal-notifier 実行結果: exit={res.returncode}")
            return res.returncode == 0
        except (subprocess.TimeoutExpired, Exception) as e:
            if debug:
                print(f"terminal-notifier エラー: {e}")
            return False
    
    # terminal-notifierの使用
    if tn:
        if _run_terminal_notifier():
            return True

    # フォールバック: AppleScript（アイコン変更不可）
    display_title = f"{name}: {title}" if name else title
    script = f'display notification "{_escape_applescript(message)}" with title "{_escape_applescript(display_title)}"'
    if subtitle:
        script += f' subtitle "{_escape_applescript(subtitle)}"'
    
    if debug:
        print("AppleScript フォールバック:", script)
    
    try:
        res = subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
        if debug:
            print(f"AppleScript 実行結果: exit={res.returncode}")
        return res.returncode == 0
    except (subprocess.TimeoutExpired, Exception) as e:
        if debug:
            print(f"AppleScript エラー: {e}")
        return False


async def wait_until_finished(progress) -> None:
    """進捗が終了するまで待つ（文字表示なし）"""
    while not progress.is_finished:
        await asyncio.sleep(0.05)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="avis_speech",
        description=(
            "コマンドライン引数または標準入力のテキストを avis voice で非同期に喋らせ、"
            "テキストは macOS の通知バナーで表示します。\n"
            "例: python avis_speech.py こんにちは ご主人様\n"
            "    echo 'おはようございます' | python avis_speech.py"
        ),
    )
    p.add_argument(
        "text",
        nargs="*",
        help="喋らせたいテキスト（未指定時は標準入力を使用）",
    )
    p.add_argument("--host", default="127.0.0.1", help="音声サーバーのホスト (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=10101, help="音声サーバーのポート (default: 10101)")
    p.add_argument(
        "--speaker",
        type=int,
        default=888753760,  # プロジェクトのデフォルト（avis 相当のボイス ID を想定）
        help="使用するスピーカー ID (default: 888753760)",
    )
    # 通知を無効化（別名 --no-display も維持）
    p.add_argument("--no-notify", dest="no_notify", action="store_true", help="通知表示を無効化（音声のみ再生）")
    p.add_argument("--no-display", dest="no_notify", action="store_true", help="通知表示を無効化（音声のみ再生）")
    # 通知アイコンの指定（terminal-notifier 使用時のみ有効）
    p.add_argument("--icon", dest="icon", help="通知アイコンのパス（右側: contentImage）。例: static/images/maid_icon.png")
    p.add_argument("--right-icon", dest="right_icon", help="右側アイコン（contentImage）を明示指定。--icon と同義")
    p.add_argument("--left-icon", dest="left_icon", help="左側アイコン（appIcon）を指定。環境により反映されない場合があります。")
    # 通知の送信元アプリ（bundle identifier）。指定時はそのアプリのアイコンが使われることがあります。
    p.add_argument("--sender", dest="sender", help="通知の sender (Bundle ID)。例: com.apple.Terminal")
    # デバッグ
    p.add_argument("--debug-notify", dest="debug_notify", action="store_true", help="通知コマンドを表示")
    # terminal-notifier のフルパスを直接指定
    p.add_argument("--terminal-notifier", dest="tn_path", help="terminal-notifier のパス（例: /opt/homebrew/bin/terminal-notifier）")
    # 左側のアプリアイコンを隠す（透明アイコンを指定）
    p.add_argument("--show-right-icon", dest="show_right_icon", action="store_true", help="右側の画像（contentImage）を表示する")
    # 名前を指定
    p.add_argument("--name", dest="name", help="通知に表示する名前")
    # 同期実行
    p.add_argument("--sync", dest="sync_mode", action="store_true", help="同期実行（音声再生完了まで待機）")
    # alerter を優先して使う（左アイコン差し替えとの相性が良い場合あり）
    p.add_argument("--prefer-alerter", dest="prefer_alerter", action="store_true", help="alerter バックエンドを優先的に使用する")
    p.add_argument("--alerter", dest="alerter_path", help="alerter のパス（例: /opt/homebrew/bin/alerter）")
    return p


async def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # 入力テキストの決定（引数優先、なければ標準入力）
    if args.text:
        text = " ".join(args.text).strip()
    else:
        if not sys.stdin.isatty():
            text = sys.stdin.read().strip()
        else:
            text = ""

    if not text:
        parser.print_usage()
        print("error: テキストが指定されていません。引数または標準入力で指定してください。")
        return 2

    try:
        # 遅延インポート（ヘルプ表示などで依存を避ける）
        try:
            speech_mod = import_module("speech")
            speech_fn = getattr(speech_mod, "speech")
        except Exception as ie:
            print("依存モジュールの読み込みに失敗しました。'pip install -r requirements.txt' を実行してください。")
            print(f"詳細: {ie}")
            return 1

        # デフォルトは非同期モード（--syncが指定されていない場合）
        if not getattr(args, "sync_mode", False):
            # 現在の引数に--syncを追加して別プロセスで実行
            new_args = sys.argv[1:] + ["--sync"]
            
            # バックグラウンドプロセスで実行
            subprocess.Popen([sys.executable, sys.argv[0]] + new_args)
            return 0
        else:
            # 同期モードは音声再生を開始してから通知
            progress = await speech_fn(text, host=args.host, port=args.port, speaker=args.speaker)
            
        # 通知表示（macOS でのみ有効）。失敗時は静かにスキップ。
        if not args.no_notify:
            # 右側（contentImage）
            icon_path = None
            # --right-icon 優先、なければ --icon
            right_candidate = getattr(args, "right_icon", None) or getattr(args, "icon", None)
            if right_candidate and getattr(args, "show_right_icon", False):
                icon_path = right_candidate
            elif getattr(args, "show_right_icon", False):
                default_icon = os.path.join(os.path.dirname(__file__), "static", "images", "maid_icon.png")
                if os.path.exists(default_icon):
                    icon_path = default_icon
            # 左側（appIcon）
            left_icon = getattr(args, "left_icon", None)
            notify_mac(
                text,
                title="AVIS",
                icon_path=icon_path,
                left_icon_path=left_icon,
                sender=getattr(args, "sender", None),
                debug=getattr(args, "debug_notify", False),
                tn_path=getattr(args, "tn_path", None),
                prefer_alerter=getattr(args, "prefer_alerter", False),
                alerter_path=getattr(args, "alerter_path", None),
                name=getattr(args, "name", None),
                show_right_icon=getattr(args, "show_right_icon", False),
            )
            # アイコン表示のヒント
            if (icon_path or left_icon) and sys.platform == "darwin" and not shutil.which("terminal-notifier"):
                print("ヒント: アイコン付き通知には 'brew install terminal-notifier' を実行してください。")

        # 同期モードの場合は再生完了まで待機
        if getattr(args, "sync_mode", False) and progress:
            await wait_until_finished(progress)

        return 0
    except KeyboardInterrupt:
        # 中断時は静かに終了
        sys.stdout.write("\n")
        sys.stdout.flush()
        return 130
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
