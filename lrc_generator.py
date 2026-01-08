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
from datetime import timedelta
from mutagen.mp3 import MP3


class LRCGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("LRCファイルジェネレーター")
        self.root.geometry("800x600")

        # 初期化
        pygame.mixer.init()

        # 変数
        self.mp3_file = None
        self.is_playing = False
        self.is_paused = False
        self.current_time = 0
        self.lyrics_data = []  # [(timestamp, lyric), ...]
        self.mp3_length = 0

        # GUI作成
        self.create_widgets()

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

        ttk.Label(lyrics_frame, text="現在の行:").grid(row=0, column=0, sticky=tk.W)

        self.current_lyric_entry = ttk.Entry(lyrics_frame, width=60)
        self.current_lyric_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.current_lyric_entry.bind('<Return>', lambda e: self.add_timestamp())

        ttk.Button(lyrics_frame, text="タイムスタンプを記録 (Enter)", command=self.add_timestamp).grid(row=0, column=2, padx=5)

        # タイムスタンプ付き歌詞リスト
        ttk.Label(lyrics_frame, text="記録済み歌詞:").grid(row=1, column=0, sticky=(tk.W, tk.N), pady=(10, 0))

        self.lyrics_text = scrolledtext.ScrolledText(lyrics_frame, width=70, height=15)
        self.lyrics_text.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)

        # 編集ボタン
        edit_frame = ttk.Frame(lyrics_frame)
        edit_frame.grid(row=3, column=0, columnspan=3, pady=5)

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
        lyrics_frame.columnconfigure(1, weight=1)
        lyrics_frame.rowconfigure(2, weight=1)
        file_frame.columnconfigure(0, weight=1)

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

    def add_timestamp(self):
        """現在の時間で歌詞にタイムスタンプを追加"""
        lyric = self.current_lyric_entry.get().strip()

        if not lyric:
            messagebox.showwarning("警告", "歌詞を入力してください")
            return

        # タイムスタンプと歌詞を記録
        self.lyrics_data.append((self.current_time, lyric))

        # 表示更新
        self.update_lyrics_display()

        # 入力欄をクリア
        self.current_lyric_entry.delete(0, tk.END)
        self.current_lyric_entry.focus()

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
