#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LRC File Generator
MP3ファイルを再生しながら歌詞にタイムスタンプを付けてLRCファイルを作成するアプリケーション
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import pygame
import os
import threading
import queue
from datetime import timedelta
from mutagen.mp3 import MP3

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


class LRCGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("LRCファイルジェネレーター")
        self.root.geometry("850x700")

        # 初期化
        pygame.mixer.init()

        # 変数
        self.mp3_file = None
        self.is_playing = False
        self.is_paused = False
        self.current_time = 0
        self.lyrics_data = []  # [(timestamp, lyric), ...]
        self.mp3_length = 0

        # Whisper関連
        self.result_queue = queue.Queue()
        self.whisper_model = None
        self._loaded_model_name = None
        self._loaded_device = None
        self.detection_thread = None

        # GUI作成
        self.create_widgets()

        if not WHISPER_AVAILABLE:
            messagebox.showwarning(
                "依存関係エラー",
                "faster-whisper がインストールされていません。\n"
                "pip install faster-whisper を実行してください。"
            )

        # タイマー
        self.update_timer()

    def create_widgets(self):
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # ファイル選択エリア
        file_frame = ttk.LabelFrame(main_frame, text="MP3ファイル", padding="5")
        file_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        self.file_label = ttk.Label(file_frame, text="ファイルが選択されていません")
        self.file_label.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5)

        ttk.Button(file_frame, text="MP3を選択", command=self.select_mp3).grid(row=0, column=1, padx=5)

        # プレーヤーコントロール
        control_frame = ttk.LabelFrame(main_frame, text="プレーヤー", padding="5")
        control_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        ttk.Button(control_frame, text="▶ 再生", command=self.play).grid(row=0, column=0, padx=5)
        ttk.Button(control_frame, text="⏸ 一時停止", command=self.pause).grid(row=0, column=1, padx=5)
        ttk.Button(control_frame, text="⏹ 停止", command=self.stop).grid(row=0, column=2, padx=5)

        # 時間表示
        self.time_label = ttk.Label(control_frame, text="00:00.00 / 00:00.00", font=("Arial", 14))
        self.time_label.grid(row=1, column=0, columnspan=3, pady=10)

        # 歌詞入力エリア
        lyrics_frame = ttk.LabelFrame(main_frame, text="歌詞入力", padding="5")
        lyrics_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        # Sub-Row 0: モデル設定バー
        config_frame = ttk.Frame(lyrics_frame)
        config_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 5))

        ttk.Label(config_frame, text="Whisperモデル:").grid(row=0, column=0, padx=(0, 2))
        self.model_var = tk.StringVar(value="medium")
        ttk.OptionMenu(config_frame, self.model_var, "medium", "small", "medium", "large-v3").grid(
            row=0, column=1, padx=(0, 15))

        ttk.Label(config_frame, text="デバイス:").grid(row=0, column=2, padx=(0, 2))
        self.device_var = tk.StringVar(value="cpu")
        ttk.OptionMenu(config_frame, self.device_var, "auto", "auto", "cpu", "cuda").grid(
            row=0, column=3)

        # Sub-Row 1: 歌詞テキスト入力ラベル
        ttk.Label(lyrics_frame, text="歌詞テキスト（1行につき1フレーズ）:").grid(
            row=1, column=0, sticky=tk.W)

        # Sub-Row 2: 歌詞一括入力テキストエリア
        self.input_lyrics_text = scrolledtext.ScrolledText(lyrics_frame, width=70, height=10)
        self.input_lyrics_text.grid(
            row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        # Sub-Row 3: 自動検出ボタン + プログレスバー + ステータス
        detect_frame = ttk.Frame(lyrics_frame)
        detect_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        self.detect_button = ttk.Button(
            detect_frame, text="自動タイムスタンプ検出", command=self.start_detection)
        self.detect_button.grid(row=0, column=0, padx=5)

        self.progress_bar = ttk.Progressbar(detect_frame, mode="indeterminate", length=250)
        self.progress_bar.grid(row=0, column=1, padx=10)

        self.status_label = ttk.Label(detect_frame, text="待機中", foreground="gray")
        self.status_label.grid(row=0, column=2, padx=5)

        # Sub-Row 4: 記録済み歌詞ラベル
        ttk.Label(lyrics_frame, text="記録済み歌詞（タイムスタンプ付き）:").grid(
            row=4, column=0, sticky=(tk.W, tk.N), pady=(10, 0))

        # Sub-Row 5: 記録済み歌詞表示
        self.lyrics_text = scrolledtext.ScrolledText(lyrics_frame, width=70, height=8)
        self.lyrics_text.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        # Sub-Row 6: 編集ボタン
        edit_frame = ttk.Frame(lyrics_frame)
        edit_frame.grid(row=6, column=0, columnspan=3, pady=5)

        ttk.Button(edit_frame, text="最後の行を削除", command=self.delete_last).grid(row=0, column=0, padx=5)
        ttk.Button(edit_frame, text="すべてクリア", command=self.clear_all).grid(row=0, column=1, padx=5)

        # 保存エリア
        save_frame = ttk.LabelFrame(main_frame, text="保存", padding="5")
        save_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        ttk.Button(save_frame, text="LRCファイルとして保存", command=self.save_lrc,
                  style='Accent.TButton').grid(row=0, column=0, padx=5, pady=5)

        # グリッド設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        lyrics_frame.columnconfigure(0, weight=1)
        lyrics_frame.rowconfigure(2, weight=1)
        lyrics_frame.rowconfigure(5, weight=1)
        file_frame.columnconfigure(0, weight=1)

    def _resolve_device(self) -> str:
        """デバイス設定を解決する。autoの場合はCUDA優先で自動判定。"""
        choice = self.device_var.get()
        if choice == "auto":
            try:
                import ctranslate2
                supported = ctranslate2.get_supported_compute_types("cuda")
                if supported:
                    return "cuda"
            except Exception:
                pass
            return "cpu"
        return choice

    def start_detection(self):
        """自動タイムスタンプ検出を開始する。"""
        if not WHISPER_AVAILABLE:
            messagebox.showerror("エラー", "faster-whisper が未インストールです\npip install faster-whisper を実行してください")
            return
        if not self.mp3_file:
            messagebox.showwarning("警告", "MP3ファイルを選択してください")
            return

        raw_text = self.input_lyrics_text.get("1.0", tk.END).strip()
        if not raw_text:
            messagebox.showwarning("警告", "歌詞テキストを入力してください")
            return

        if self.detection_thread and self.detection_thread.is_alive():
            messagebox.showwarning("警告", "現在解析中です。完了をお待ちください")
            return

        lyric_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        self.detect_button.config(state="disabled")
        self.progress_bar.start(10)
        self.status_label.config(text="初期化中...", foreground="blue")

        self.detection_thread = threading.Thread(
            target=self._run_whisper,
            args=(lyric_lines,),
            daemon=True
        )
        self.detection_thread.start()
        self.root.after(100, self._poll_result_queue)

    def _run_whisper(self, lyric_lines: list):
        """バックグラウンドスレッドでWhisperを実行する。"""
        try:
            model_name = self.model_var.get()
            device = self._resolve_device()
            compute_type = "int8_float16" if device == "cuda" else "int8"

            # モデルキャッシュ: 同一モデル/デバイスなら再利用
            if (self.whisper_model is None
                    or self._loaded_model_name != model_name
                    or self._loaded_device != device):
                self.result_queue.put(("status", f"モデル '{model_name}' を読み込み中（初回はDL含む）..."))
                try:
                    self.whisper_model = WhisperModel(
                        model_name, device=device, compute_type=compute_type
                    )
                except Exception:
                    # CUDAライブラリ未インストール等の場合はCPUにフォールバック
                    device = "cpu"
                    compute_type = "int8"
                    self.result_queue.put(("status", "GPU初期化失敗 → CPUで実行します..."))
                    self.whisper_model = WhisperModel(
                        model_name, device=device, compute_type=compute_type
                    )
                self._loaded_model_name = model_name
                self._loaded_device = device

            self.result_queue.put(("status", "音声解析中（しばらくお待ちください）..."))

            segments, info = self.whisper_model.transcribe(
                self.mp3_file,
                language="ja",
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500}
            )
            segment_list = list(segments)

            self.result_queue.put(("status", f"{len(segment_list)}セグメント検出 → 歌詞を対応付け中..."))
            aligned = self._align_lyrics(lyric_lines, segment_list)
            self.result_queue.put(("done", aligned))

        except Exception as e:
            import traceback
            self.result_queue.put(("error", f"{str(e)}\n{traceback.format_exc()}"))

    def _align_lyrics(self, lyric_lines: list, segments: list) -> list:
        """Whisperセグメントとユーザー歌詞行を比率マッピングで対応付ける。"""
        n_lines = len(lyric_lines)
        n_segs = len(segments)

        if n_segs == 0:
            interval = self.mp3_length / max(n_lines, 1) if self.mp3_length > 0 else 0
            return [(i * interval, line) for i, line in enumerate(lyric_lines)]

        if n_lines == n_segs:
            return [(seg.start, line) for seg, line in zip(segments, lyric_lines)]

        result = []
        for i, line in enumerate(lyric_lines):
            if n_lines == 1:
                seg_idx = 0
            else:
                seg_idx = round(i * (n_segs - 1) / (n_lines - 1))
            seg_idx = max(0, min(seg_idx, n_segs - 1))
            result.append((segments[seg_idx].start, line))

        ratio = abs(n_lines - n_segs) / max(n_lines, n_segs)
        if ratio > 0.5:
            self.result_queue.put((
                "status",
                f"[注意] 歌詞{n_lines}行 vs セグメント{n_segs}個（差異{ratio*100:.0f}%）- 手動修正を推奨"
            ))
        return result

    def _poll_result_queue(self):
        """メインスレッドで定期的にキューをチェックしてUI更新する。"""
        try:
            while True:
                msg_type, payload = self.result_queue.get_nowait()
                if msg_type == "status":
                    self.status_label.config(text=payload, foreground="blue")
                elif msg_type == "done":
                    self.lyrics_data = payload
                    self.update_lyrics_display()
                    self.progress_bar.stop()
                    self.detect_button.config(state="normal")
                    self.status_label.config(
                        text=f"完了 - {len(payload)}行を検出", foreground="green")
                    return
                elif msg_type == "error":
                    messagebox.showerror("解析エラー", payload[:500])
                    self.progress_bar.stop()
                    self.detect_button.config(state="normal")
                    self.status_label.config(text="エラーが発生しました", foreground="red")
                    return
        except queue.Empty:
            pass
        self.root.after(100, self._poll_result_queue)

    def select_mp3(self):
        """MP3ファイルを選択"""
        file_path = filedialog.askopenfilename(
            title="MP3ファイルを選択",
            filetypes=[("MP3ファイル", "*.mp3"), ("すべてのファイル", "*.*")]
        )

        if file_path:
            self.mp3_file = file_path
            self.file_label.config(text=os.path.basename(file_path))

            # MP3の長さを取得
            try:
                audio = MP3(file_path)
                self.mp3_length = audio.info.length
            except:
                self.mp3_length = 0

            # 既存の再生を停止
            if self.is_playing:
                self.stop()

            messagebox.showinfo("成功", "MP3ファイルを読み込みました")

    def play(self):
        """再生"""
        if not self.mp3_file:
            messagebox.showwarning("警告", "MP3ファイルを選択してください")
            return

        if self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.is_playing = True
        elif not self.is_playing:
            try:
                pygame.mixer.music.load(self.mp3_file)
                pygame.mixer.music.play()
                self.is_playing = True
                self.current_time = 0
            except Exception as e:
                messagebox.showerror("エラー", f"再生エラー: {str(e)}")

    def pause(self):
        """一時停止"""
        if self.is_playing and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused = True

    def stop(self):
        """停止"""
        pygame.mixer.music.stop()
        self.is_playing = False
        self.is_paused = False
        self.current_time = 0

    def update_timer(self):
        """タイマー更新"""
        if self.is_playing and not self.is_paused:
            if pygame.mixer.music.get_busy():
                # pygameの再生位置を取得（ミリ秒）
                self.current_time = pygame.mixer.music.get_pos() / 1000.0

                # 表示更新
                current_str = self.format_time(self.current_time)
                total_str = self.format_time(self.mp3_length)
                self.time_label.config(text=f"{current_str} / {total_str}")
            else:
                # 再生終了
                self.is_playing = False
                self.current_time = 0

        # 100ms後に再度実行
        self.root.after(100, self.update_timer)

    def format_time(self, seconds):
        """秒数を [mm:ss.xx] 形式に変換"""
        if seconds < 0:
            seconds = 0
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes:02d}:{secs:05.2f}"

    def format_lrc_time(self, seconds):
        """秒数を LRC形式 [mm:ss.xx] に変換"""
        if seconds < 0:
            seconds = 0
        minutes = int(seconds // 60)
        secs = seconds % 60
        centiseconds = int((secs % 1) * 100)
        secs_int = int(secs)
        return f"[{minutes:02d}:{secs_int:02d}.{centiseconds:02d}]"

    def update_lyrics_display(self):
        """歌詞表示を更新"""
        self.lyrics_text.delete(1.0, tk.END)

        # タイムスタンプでソート
        sorted_lyrics = sorted(self.lyrics_data, key=lambda x: x[0])

        for timestamp, lyric in sorted_lyrics:
            time_str = self.format_lrc_time(timestamp)
            self.lyrics_text.insert(tk.END, f"{time_str} {lyric}\n")

    def delete_last(self):
        """最後の行を削除"""
        if self.lyrics_data:
            self.lyrics_data.pop()
            self.update_lyrics_display()

    def clear_all(self):
        """すべてクリア"""
        if messagebox.askyesno("確認", "すべての歌詞データを削除しますか？"):
            self.lyrics_data.clear()
            self.update_lyrics_display()

    def save_lrc(self):
        """LRCファイルとして保存"""
        if not self.lyrics_data:
            messagebox.showwarning("警告", "歌詞データがありません")
            return

        # 保存先を選択
        file_path = filedialog.asksaveasfilename(
            title="LRCファイルを保存",
            defaultextension=".lrc",
            filetypes=[("LRCファイル", "*.lrc"), ("すべてのファイル", "*.*")]
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # メタデータ（オプション）
                if self.mp3_file:
                    f.write(f"[ti:{os.path.splitext(os.path.basename(self.mp3_file))[0]}]\n")
                f.write("[ar:]\n")
                f.write("[al:]\n")
                f.write("[by:LRC Generator]\n")
                f.write("\n")

                # タイムスタンプでソート
                sorted_lyrics = sorted(self.lyrics_data, key=lambda x: x[0])

                # 歌詞を書き込み
                for timestamp, lyric in sorted_lyrics:
                    time_str = self.format_lrc_time(timestamp)
                    f.write(f"{time_str}{lyric}\n")

            messagebox.showinfo("成功", f"LRCファイルを保存しました:\n{file_path}")
        except Exception as e:
            messagebox.showerror("エラー", f"保存エラー: {str(e)}")


def main():
    root = tk.Tk()
    app = LRCGenerator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
