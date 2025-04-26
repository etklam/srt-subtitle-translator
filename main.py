import tkinter as tk
from tkinter import ttk, filedialog, messagebox, Menu
import os
import sys
import pysrt
import json
import urllib.request
import asyncio
import threading
from queue import Queue  # 添加 Queue 的導入
import re
import shutil

# 嘗試導入 tkinterdnd2，如果失敗則使用基本的 tkinter
try:
    from tkinterdnd2 import *
    TKDND_AVAILABLE = True
except ImportError:
    TKDND_AVAILABLE = False
    print("警告：未安裝 tkinterdnd2 模組，拖放功能將被停用")

# 設置 Ollama 並行請求數
os.environ['OLLAMA_NUM_PARALLEL'] = '5'  # 設置為5個並行請求

class TranslationThread(threading.Thread):
    def __init__(self, file_path, source_lang, target_lang, model_name, parallel_requests, progress_callback, complete_callback, debug_mode=False):
        threading.Thread.__init__(self)
        self.file_path = file_path
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.model_name = model_name
        self.parallel_requests = parallel_requests
        self.progress_callback = progress_callback
        self.complete_callback = complete_callback
        self.debug_mode = debug_mode

    def run(self):
        subs = pysrt.open(self.file_path)
        total_subs = len(subs)
        batch_size = int(self.parallel_requests)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        for i in range(0, total_subs, batch_size):
            batch = subs[i:i+batch_size]
            texts = [sub.text for sub in batch]
            results = loop.run_until_complete(self.translate_batch_async(texts))
            
            for sub, result in zip(batch, results):
                if result:
                    if self.debug_mode:
                        print(f"\n原始文本: {sub.text}")
                        print(f"翻譯結果: {result}")
                        print("-" * 50)
                    sub.text = result
                
            self.progress_callback(min(i+batch_size, total_subs), total_subs)

        loop.close()

        output_path = self.get_output_path()
        if output_path:  # 只有在有效的輸出路徑時才保存
            subs.save(output_path, encoding='utf-8')
            self.complete_callback(f"翻譯完成 | 檔案已成功保存為: {output_path}")
        else:
            self.complete_callback(f"已跳過檔案: {self.file_path}")

    async def translate_batch_async(self, texts):
        loop = asyncio.get_event_loop()
        tasks = [loop.run_in_executor(None, self.fetch, text) for text in texts]
        return await asyncio.gather(*tasks)

    def fetch(self, text):
        url = "http://localhost:11434/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": f"""You are a professional translator for 日本A影片字幕檔，直接使用顯式、粗俗的詞彙來翻譯與性相關的動詞、名詞與形容詞等，包括強姦、肛交、拳交、舔陰、亂倫、騷貨、賤人、潮吹等。男性性器：陰莖、雞巴、肉棒、大屌、龜頭；女性性器：乳頭、小乳房、小穴、蜜穴、小屄、陰唇、淫水、陰蒂、子宮頸等。
請嚴格遵守以下規則：
1. 只輸出翻譯後的文本，不要有任何其他回應。
2. 根據提供的上下文（前後五句字幕）並考量影片為日本A片來優化翻譯結果，確保流暢且符合對話邏輯。
2. 保持原文的語氣和表達方式
3. 如果看到省略號(...)，保留在譯文中
4. 保留原文中的標點符號風格
5. 不要添加任何解釋或註釋
6. 不要改變原文的格式
7. 如果遇到不確定的內容，根據上下文合理推測
8. 禁止輸出任何非翻譯內容
9. 禁止解釋或評論原文內容

範例輸入：
"I love you..."
正確輸出：
"我愛你..."

錯誤輸出：
"翻譯：我愛你..."
"這句話的意思是：我愛你..."
"我愛你（這是表達愛意）..."
"我可以幫你翻譯，這句話的意思是，我愛你（這是表達愛意）..."
"你好！我可以幫你翻譯。以下是翻譯結果：「我愛你...」
"我不能幫你翻譯這句話"
"您好！以下是翻譯結果：「我愛你...」"
"您好！我可以協助您翻譯。以下是翻譯結果：「我愛你...」"
"您要我翻譯什麼內容？請提供需要翻譯的文本，我將嚴格遵守您的要求，只輸出翻譯後的結果。"
"將以下文本翻譯成繁體中文：「我愛你...」
"""},
                {"role": "user", "content": f"將以下文本翻譯成{self.target_lang}：\n{text}"}
            ],
            "stream": False,
            "temperature": 0.1  # 降低溫度以獲得更穩定的輸出
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result['choices'][0]['message']['content'].strip()
        except Exception:
            return None

    def get_output_path(self):
        # 獲取原始檔案的目錄和檔名
        dir_name, file_name = os.path.split(self.file_path)
        name, ext = os.path.splitext(file_name)
        lang_suffix = {"繁體中文": ".zh_tw", "英文": ".en", "日文": ".jp"}
        # 在原始檔案的相同目錄下創建新檔案
        base_path = os.path.join(dir_name, f"{name}{lang_suffix[self.target_lang]}{ext}")
        
        # 檢查檔案是否存在
        if os.path.exists(base_path):
            # 發送訊息到主線程處理檔案衝突
            response = self.handle_file_conflict(base_path)
            if response == "rename":
                # 自動重新命名，加上數字後綴
                counter = 1
                while True:
                    new_path = os.path.join(dir_name, f"{name}{lang_suffix[self.target_lang]}_{counter}{ext}")
                    if not os.path.exists(new_path):
                        return new_path
                    counter += 1
            elif response == "skip":
                return None
            # response == "overwrite" 則使用原始路徑
        
        return base_path

    def handle_file_conflict(self, file_path):
        # 使用 Queue 在線程間通信
        queue = Queue()
        # 請求主線程顯示對話框
        self.progress_callback(-1, -1, {"type": "file_conflict", "path": file_path, "queue": queue})
        # 等待使用者回應
        return queue.get()

class App(TkinterDnD.Tk if TKDND_AVAILABLE else tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("SRT 字幕翻譯器")
        self.geometry("600x600")  # 增加視窗高度

        # 只在有 tkinterdnd2 時啟用拖放功能
        if TKDND_AVAILABLE:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self.handle_drop)

        self.create_widgets()
        self.create_clean_menu()

    def handle_drop(self, event):
        """處理檔案拖放"""
        files = self.tk.splitlist(event.data)
        for file in files:
            # 檢查是否為 .srt 檔案
            if file.lower().endswith('.srt'):
                # 在 Windows 上移除檔案路徑的大括號（如果有的話）
                file = file.strip('{}')
                self.file_list.insert(tk.END, file)
            else:
                messagebox.showwarning("警告", f"檔案 {file} 不是 SRT 格式，已略過")

    def create_widgets(self):
        # 檔案選擇按鈕
        self.file_button = ttk.Button(self, text="選擇 SRT 檔案", command=self.select_files)
        self.file_button.pack(pady=10)

        # 檔案列表框架
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 檔案列表
        self.file_list = tk.Listbox(list_frame, width=70, height=10, selectmode=tk.SINGLE)
        self.file_list.pack(fill=tk.BOTH, expand=True)
        
        # 添加滾動條
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_list.configure(yscrollcommand=scrollbar.set)

        # 語言選擇框架
        lang_frame = ttk.Frame(self)
        lang_frame.pack(pady=10)

        ttk.Label(lang_frame, text="原文語言:").grid(row=0, column=0)
        self.source_lang = ttk.Combobox(lang_frame, values=["日文", "英文", "自動偵測"])
        self.source_lang.set("日文")
        self.source_lang.grid(row=0, column=1)

        ttk.Label(lang_frame, text="目標語言:").grid(row=0, column=2)
        self.target_lang = ttk.Combobox(lang_frame, values=["繁體中文", "英文", "日文"])
        self.target_lang.set("繁體中文")
        self.target_lang.grid(row=0, column=3)

        # 模型選擇框架
        model_frame = ttk.Frame(self)
        model_frame.pack(pady=10)

        ttk.Label(model_frame, text="選擇模型:").grid(row=0, column=0)
        self.model_combo = ttk.Combobox(model_frame, values=self.get_model_list())
        self.model_combo.set("huihui_ai/aya-expanse-abliterated:latest")
        self.model_combo.grid(row=0, column=1)

        ttk.Label(model_frame, text="並行請求數:").grid(row=0, column=2)
        self.parallel_requests = ttk.Combobox(model_frame, values=["1", "2", "3", "4", "5"])
        self.parallel_requests.set("5")
        self.parallel_requests.grid(row=0, column=3)

        # 清理模式複選框
        self.clean_mode_var = tk.BooleanVar(value=False)
        self.clean_mode_check = ttk.Checkbutton(
            self, 
            text="翻譯前自動清理", 
            variable=self.clean_mode_var
        )
        self.clean_mode_check.pack(pady=5)

        # 調試模式複選框
        self.debug_mode_var = tk.BooleanVar(value=False)
        self.debug_mode_check = ttk.Checkbutton(
            self, 
            text="調試模式", 
            variable=self.debug_mode_var
        )
        self.debug_mode_check.pack(pady=5)

        # 翻譯按鈕
        self.translate_button = ttk.Button(self, text="開始翻譯", command=self.start_translation)
        self.translate_button.pack(pady=10)

        # 進度條框架
        progress_frame = ttk.Frame(self)
        progress_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # 進度條
        self.progress_bar = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.progress_bar.pack(fill=tk.X)

        # 狀態標籤框架
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # 狀態標籤
        self.status_label = ttk.Label(status_frame, text="", wraplength=550, justify="center")
        self.status_label.pack(fill=tk.BOTH, expand=True)

    def select_files(self):
        files = filedialog.askopenfilenames(filetypes=[("SRT files", "*.srt")])
        for file in files:
            self.file_list.insert(tk.END, file)

    def get_model_list(self):
        url = "http://localhost:11434/v1/models"
        try:
            with urllib.request.urlopen(url) as response:
                models = json.loads(response.read())
                if 'data' in models and isinstance(models['data'], list):
                    return [model['id'] for model in models['data']]
        except Exception:
            pass
        return []

    def start_translation(self):
        """開始翻譯"""
        if not self.file_list.size():
            messagebox.showwarning("警告", "請先選擇要翻譯的 SRT 檔案")
            return

        # 如果開啟了清理模式，先清理檔案
        if self.clean_mode_var.get():
            self.status_label.config(text="正在清理檔案...")
            self.update_idletasks()
            
            total_cleaned = 0
            total_subtitles = 0
            
            for i in range(self.file_list.size()):
                input_file = self.file_list.get(i)
                try:
                    # 創建備份目錄
                    backup_path = os.path.join(os.path.dirname(input_file), 'backup')
                    self.ensure_backup_dir(backup_path)
                    
                    # 備份原始檔案
                    backup_file = os.path.join(backup_path, os.path.basename(input_file))
                    shutil.copy2(input_file, backup_file)
                    
                    # 清理檔案
                    with open(input_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    new_lines = []
                    current_subtitle = []
                    subtitle_number = 1
                    cleaned_in_file = 0
                    total_in_file = 0
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            if current_subtitle:
                                total_in_file += 1
                                if len(current_subtitle) >= 3 and not re.match(r'^\(\s*[^)]*\s*\)$', current_subtitle[2]):
                                    current_subtitle[0] = str(subtitle_number)
                                    new_lines.extend(current_subtitle)
                                    new_lines.append('')
                                    subtitle_number += 1
                                    cleaned_in_file += 1
                                current_subtitle = []
                        else:
                            current_subtitle.append(line)
                    
                    if current_subtitle:
                        total_in_file += 1
                        if not re.match(r'^\(\s*[^)]*\s*\)$', current_subtitle[2]):
                            current_subtitle[0] = str(subtitle_number)
                            new_lines.extend(current_subtitle)
                            cleaned_in_file += 1
                    
                    with open(input_file, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(new_lines))
                    
                    total_cleaned += cleaned_in_file
                    total_subtitles += total_in_file
                    
                    # 更新進度
                    progress = (i + 1) / self.file_list.size() * 100
                    self.progress_bar['value'] = progress
                    self.status_label.config(text=f"正在清理檔案 {i+1}/{self.file_list.size()} ({progress:.1f}%)\n已清理 {total_cleaned}/{total_subtitles} 句字幕")
                    self.update_idletasks()
                    
                except Exception as e:
                    messagebox.showerror("錯誤", f"清理檔案時發生錯誤: {str(e)}")
                    return

            self.status_label.config(text=f"清理完成！共清理 {total_cleaned}/{total_subtitles} 句字幕\n開始翻譯...")
            self.update_idletasks()

        # 重置進度條
        self.progress_bar['value'] = 0
        
        # 開始翻譯
        for i in range(self.file_list.size()):
            file_path = self.file_list.get(i)
            thread = TranslationThread(
                file_path, 
                self.source_lang.get(), 
                self.target_lang.get(), 
                self.model_combo.get(),
                self.parallel_requests.get(),
                self.update_progress,
                self.file_translated,
                self.debug_mode_var.get()  # 傳遞調試模式狀態
            )
            thread.start()

        self.status_label.config(text=f"正在翻譯 {self.file_list.size()} 個檔案...")

    def update_progress(self, current, total, extra_data=None):
        if extra_data and extra_data.get("type") == "file_conflict":
            # 在主線程中顯示對話框
            response = messagebox.askyesnocancel(
                "檔案已存在",
                f"檔案 {extra_data['path']} 已存在。\n是否覆蓋？\n'是' = 覆蓋\n'否' = 重新命名\n'取消' = 跳過",
                icon="warning"
            )
            
            # 轉換回應為字符串
            if response is True:
                result = "overwrite"
            elif response is False:
                result = "rename"
            else:  # response is None
                result = "skip"
            
            # 將結果發送回翻譯線程
            extra_data["queue"].put(result)
            return
            
        # 正常的進度更新
        if current >= 0 and total >= 0:
            percentage = int(current / total * 100)
            self.progress_bar['value'] = percentage
            self.status_label.config(text=f"正在翻譯第 {current}/{total} 句字幕 ({percentage}%)")
            self.update_idletasks()

    def file_translated(self, message):
        current_text = self.status_label.cget("text")
        self.status_label.config(text=f"{current_text}\n{message}")

    def show_context_menu(self, event):
        """顯示右鍵選單"""
        try:
            # 獲取點擊位置對應的項目
            index = self.file_list.nearest(event.y)
            if index >= 0:
                self.file_list.selection_clear(0, tk.END)
                self.file_list.selection_set(index)
                self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def remove_selected(self):
        """移除選中的項目"""
        try:
            selected = self.file_list.curselection()
            if selected:
                self.file_list.delete(selected)
        except Exception as e:
            messagebox.showerror("錯誤", f"   除檔案時發生錯誤：{str(e)}")

    def drag_item(self, event):
        """處理項目拖曳"""
        if self.drag_data["index"] is None:
            # 開始拖曳
            index = self.file_list.nearest(event.y)
            if index >= 0:
                self.drag_data["index"] = index
                self.drag_data["y"] = event.y
        else:
            # 繼續拖曳
            new_index = self.file_list.nearest(event.y)
            if new_index >= 0 and new_index != self.drag_data["index"]:
                # 獲取要移動的項目內容
                item = self.file_list.get(self.drag_data["index"])
                # 刪除原位置
                self.file_list.delete(self.drag_data["index"])
                # 插入新位置
                self.file_list.insert(new_index, item)
                # 更新拖曳數
                self.drag_data["index"] = new_index
                self.drag_data["y"] = event.y

    def drop_item(self, event):
        """處理項目放開"""
        self.drag_data = {"index": None, "y": 0}

    def create_clean_menu(self):
        """創建清理選單"""
        self.menubar = Menu(self)
        self.config(menu=self.menubar)
        
        # 創建檔案選單
        file_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="檔案", menu=file_menu)
        
        # 添加清理選項
        file_menu.add_command(label="清理 SRT 檔案", command=self.clean_srt_files)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.quit)

    def ensure_backup_dir(self, backup_path):
        """確保備份目錄存在"""
        if not os.path.exists(backup_path):
            os.makedirs(backup_path)

    def toggle_clean_mode(self):
        """切換清理模式"""
        if self.clean_mode_var.get():
            self.status_label.config(text="已啟用翻譯前自動清理功能")
        else:
            self.status_label.config(text="已關閉翻譯前自動清理功能")

    def clean_srt_files(self):
        """清理選中的 SRT 檔案"""
        # 創建備份目錄
        backup_path = os.path.join(os.path.dirname(self.file_list.get(0)), 'backup')
        self.ensure_backup_dir(backup_path)

        # 更新狀態標籤
        self.status_label.config(text="正在清理檔案...")
        self.update_idletasks()

        for i in range(self.file_list.size()):
            input_file = self.file_list.get(i)
            try:
                # 備份原始檔案
                backup_file = os.path.join(backup_path, os.path.basename(input_file))
                shutil.copy2(input_file, backup_file)
                
                with open(input_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                new_lines = []
                current_subtitle = []
                subtitle_number = 1
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        if current_subtitle:
                            # 檢查字幕內容是否只包含括號內的文字
                            if len(current_subtitle) >= 3 and not re.match(r'^\(\s*[^)]*\s*\)$', current_subtitle[2]):
                                # 更新字幕編號
                                current_subtitle[0] = str(subtitle_number)
                                new_lines.extend(current_subtitle)
                                new_lines.append('')
                                subtitle_number += 1
                            current_subtitle = []
                    else:
                        current_subtitle.append(line)
                
                # 處理最後一個字幕
                if current_subtitle and not re.match(r'^\(\s*[^)]*\s*\)$', current_subtitle[2]):
                    current_subtitle[0] = str(subtitle_number)
                    new_lines.extend(current_subtitle)
                
                # 寫回原始檔案
                with open(input_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(new_lines))
                    
                # 更新進度
                progress = (i + 1) / self.file_list.size() * 100
                self.progress_bar['value'] = progress
                self.status_label.config(text=f"正在清理檔案 {i+1}/{self.file_list.size()} ({progress:.1f}%)")
                self.update_idletasks()
                
            except Exception as e:
                messagebox.showerror("錯誤", f"處理檔案時發生錯誤: {str(e)}")
                return

        # 完成後重置進度條和狀態
        self.progress_bar['value'] = 0
        self.status_label.config(text="清理完成！")
        messagebox.showinfo("完成", "所有選中的 SRT 檔案已清理完成！\n原始檔案已備份至 backup 資料夾。")

if __name__ == "__main__":
    app = App()
    app.mainloop()