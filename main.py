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
    def __init__(self, file_path, source_lang, target_lang, model_name, parallel_requests, progress_callback, complete_callback, debug_mode=False, replace_original=False):
        threading.Thread.__init__(self)
        self.file_path = file_path
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.model_name = model_name
        self.parallel_requests = parallel_requests
        self.progress_callback = progress_callback
        self.complete_callback = complete_callback
        self.debug_mode = debug_mode
        self.app = None
        self.replace_original = replace_original

    def set_app(self, app):
        """設置對 App 實例的引用"""
        self.app = app

    def run(self):
        subs = pysrt.open(self.file_path)
        total_subs = len(subs)
        batch_size = int(self.parallel_requests)

        # 如果是取代原始檔案模式，先創建備份
        if self.replace_original:
            try:
                backup_path = os.path.join(os.path.dirname(self.file_path), 'backup')
                if not os.path.exists(backup_path):
                    os.makedirs(backup_path)
                backup_file = os.path.join(backup_path, os.path.basename(self.file_path))
                shutil.copy2(self.file_path, backup_file)
            except Exception as e:
                self.complete_callback(f"警告：無法創建備份檔案：{str(e)}")

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

Incorrect output:
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
"Translation: I love you..."
"This means: I love you..."
"I love you (this is an expression of love)..."
"I can help you translate, this means: I love you (this is an expression of love)..."
"Hello! I can help you translate. Here is the translation result: 'I love you...'"
"I cannot translate this sentence"
"Hello! Here is the translation result: 'I love you...'"
"Hello! I can assist you with translation. Here is the translation result: 'I love you...'"
"Please provide the text you want to translate, and I will strictly follow your requirements and only output the translation result."
"Translate the following text to Traditional Chinese: 'I love you...'"
"""},
                {"role": "user", "content": f"Translate the following text to {self.target_lang}:\n{text}"}
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
        """獲取輸出路徑"""
        # 如果選擇取代原始檔案，直接返回原始檔案路徑
        if self.replace_original:
            return self.file_path

        # 獲取原始檔案的目錄和檔名
        dir_name, file_name = os.path.split(self.file_path)
        name, ext = os.path.splitext(file_name)
        
        lang_suffix = {
            "繁體中文": ".zh_tw", 
            "英文": ".en", 
            "日文": ".jp", 
            "韓文": ".ko", 
            "法文": ".fr", 
            "德文": ".de", 
            "西班牙文": ".es", 
            "義大利文": ".it", 
            "葡萄牙文": ".pt", 
            "俄文": ".ru", 
            "阿拉伯文": ".ar", 
            "印地文": ".hi", 
            "印尼文": ".id", 
            "越南文": ".vi", 
            "泰文": ".th", 
            "馬來文": ".ms"
        }
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
        """處理檔案衝突"""
        # 使用 Queue 在線程間通信
        queue = Queue()
        
        # 請求主線程顯示對話框
        self.progress_callback(-1, -1, {
            "type": "file_conflict",
            "path": file_path,
            "queue": queue
        })
        
        # 等待使用者回應
        return queue.get()

class App(TkinterDnD.Tk if TKDND_AVAILABLE else tk.Tk):
    def __init__(self):
        super().__init__()
        self.countdown_window = None
        
        # 初始化語言設定
        self.current_language = tk.StringVar(value="zh_tw")  # 預設使用繁體中文
        self.translations = {
            "zh_tw": {
                "window_title": "SRT 字幕翻譯器",
                "select_files": "選擇 SRT 檔案",
                "select_folder": "文件夾批量新增",
                "source_lang_label": "原文語言:",
                "target_lang_label": "目標語言:",
                "model_label": "選擇模型:",
                "parallel_label": "並行請求數:",
                "auto_clean": "翻譯前自動清理",
                "debug_mode": "調試模式",
                "clean_workspace": "翻譯後清理工作區",
                "replace_original": "取代原始檔案",
                "start_translation": "開始翻譯",
                "file_removed": "已從工作區移除選中的檔案",
                "no_files": "警告",
                "no_files_message": "請先選擇要翻譯的 SRT 檔案",
                "confirm": "確認",
                "replace_warning": "您選擇了取代原始檔案模式。\n這將會直接覆蓋原始的 SRT 檔案。\n原始檔案將會備份到 backup 資料夾。\n是否確定要繼續？",
                "cleaning": "正在清理檔案...",
                "cleaning_progress": "正在清理檔案 {}/{} ({:.1f}%)\n已清理 {}/{} 句字幕",
                "cleaning_complete": "清理完成！共清理 {}/{} 句字幕\n開始翻譯...",
                "translating": "正在翻譯 {} 個檔案...",
                "translation_progress": "正在翻譯第 {}/{} 句字幕 ({}%)",
                "all_complete": "所有檔案翻譯完成！",
                "workspace_cleaned": "所有檔案翻譯完成！工作區已清理。",
                "error": "錯誤",
                "error_message": "移除檔案時發生錯誤：{}",
                "source_lang_options": ["日文", "英文", "韓文", "法文", "德文", "西班牙文", "義大利文", "葡萄牙文", "俄文", "阿拉伯文", "印地文", "印尼文", "越南文", "泰文", "馬來文", "自動偵測"],
                "target_lang_options": ["繁體中文", "英文", "日文", "韓文", "法文", "德文", "西班牙文", "義大利文", "葡萄牙文", "俄文", "阿拉伯文", "印地文", "印尼文", "越南文", "泰文", "馬來文"],
                "switch_language": "Switch to English",
                "file_conflict_title": "檔案已存在",
                "file_conflict_message": "檔案 {} 已存在。\n請選擇處理方式：\n\n'覆蓋' = 覆蓋現有檔案\n'重新命名' = 自動重新命名\n'跳過' = 跳過此檔案",
                "overwrite": "覆蓋",
                "rename": "重新命名",
                "skip": "跳過",
                "auto_rename_countdown": "{} 秒後自動重新命名"
            },
            "en": {
                "window_title": "SRT Subtitle Translator",
                "select_files": "Select SRT Files",
                "select_folder": "Add Folder",
                "source_lang_label": "Source Language:",
                "target_lang_label": "Target Language:",
                "model_label": "Select Model:",
                "parallel_label": "Parallel Requests:",
                "auto_clean": "Auto Clean Before Translation",
                "debug_mode": "Debug Mode",
                "clean_workspace": "Clean Workspace After Translation",
                "replace_original": "Replace Original File",
                "start_translation": "Start Translation",
                "file_removed": "Selected file has been removed from workspace",
                "no_files": "Warning",
                "no_files_message": "Please select SRT files first",
                "confirm": "Confirm",
                "replace_warning": "You have chosen to replace original files.\nThis will overwrite the original SRT files.\nOriginal files will be backed up to the backup folder.\nDo you want to continue?",
                "cleaning": "Cleaning files...",
                "cleaning_progress": "Cleaning files {}/{} ({:.1f}%)\nCleaned {}/{} subtitles",
                "cleaning_complete": "Cleaning complete! Cleaned {}/{} subtitles\nStarting translation...",
                "translating": "Translating {} files...",
                "translation_progress": "Translating subtitle {}/{} ({}%)",
                "all_complete": "All files have been translated!",
                "workspace_cleaned": "All files have been translated! Workspace has been cleaned.",
                "error": "Error",
                "error_message": "Error removing file: {}",
                "source_lang_options": ["Japanese", "English", "Korean", "French", "German", "Spanish", "Italian", "Portuguese", "Russian", "Arabic", "Hindi", "Indonesian", "Vietnamese", "Thai", "Malay", "Auto Detect"],
                "target_lang_options": ["Traditional Chinese", "English", "Japanese", "Korean", "French", "German", "Spanish", "Italian", "Portuguese", "Russian", "Arabic", "Hindi", "Indonesian", "Vietnamese", "Thai", "Malay"],
                "switch_language": "切換至中文",
                "file_conflict_title": "File Exists",
                "file_conflict_message": "File {} already exists.\nPlease choose an action:\n\n'Overwrite' = Replace existing file\n'Rename' = Auto rename\n'Skip' = Skip this file",
                "overwrite": "Overwrite",
                "rename": "Rename",
                "skip": "Skip",
                "auto_rename_countdown": "Auto rename in {} seconds"
            }
        }

        self.title(self.get_text("window_title"))
        self.geometry("600x600")

        # 只在有 tkinterdnd2 時啟用拖放功能
        if TKDND_AVAILABLE:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self.handle_drop)

        # 初始化變數
        self.clean_mode_var = tk.BooleanVar(value=False)
        self.debug_mode_var = tk.BooleanVar(value=False)
        self.auto_clean_workspace_var = tk.BooleanVar(value=True)
        self.replace_original_var = tk.BooleanVar(value=False)

        self.create_widgets()
        self.create_clean_menu()

    def get_text(self, key):
        """獲取當前語言的文字"""
        return self.translations[self.current_language.get()].get(key, key)

    def switch_language(self):
        """切換語言"""
        current = self.current_language.get()
        new_language = "en" if current == "zh_tw" else "zh_tw"
        self.current_language.set(new_language)
        self.update_ui_language()

    def update_ui_language(self):
        """更新UI語言"""
        # 更新視窗標題
        self.title(self.get_text("window_title"))
        
        # 更新語言切換按鈕
        self.lang_button.config(text=self.get_text("switch_language"))
        
        # 更新按鈕文字
        self.file_button.config(text=self.get_text("select_files"))
        self.folder_button.config(text=self.get_text("select_folder"))
        self.translate_button.config(text=self.get_text("start_translation"))
        
        # 更新標籤文字
        self.source_lang_label.config(text=self.get_text("source_lang_label"))
        self.target_lang_label.config(text=self.get_text("target_lang_label"))
        self.model_label.config(text=self.get_text("model_label"))
        self.parallel_label.config(text=self.get_text("parallel_label"))
        
        # 更新複選框文字
        self.clean_mode_check.config(text=self.get_text("auto_clean"))
        self.debug_mode_check.config(text=self.get_text("debug_mode"))
        self.auto_clean_workspace_check.config(text=self.get_text("clean_workspace"))
        self.replace_original_check.config(text=self.get_text("replace_original"))

        # 更新下拉選單選項
        current_source = self.source_lang.get()
        current_target = self.target_lang.get()
        
        # 更新語言選項
        source_options = self.translations[self.current_language.get()]["source_lang_options"]
        target_options = self.translations[self.current_language.get()]["target_lang_options"]
        
        self.source_lang['values'] = source_options
        self.target_lang['values'] = target_options
        
        # 保持選擇的值，但轉換語言
        if self.current_language.get() == "en":
            if current_source == "日文":
                self.source_lang.set("Japanese")
            elif current_source == "英文":
                self.source_lang.set("English")
            elif current_source == "自動偵測":
                self.source_lang.set("Auto Detect")
                
            if current_target == "繁體中文":
                self.target_lang.set("Traditional Chinese")
            elif current_target == "英文":
                self.target_lang.set("English")
            elif current_target == "日文":
                self.target_lang.set("Japanese")
        else:
            if current_source == "Japanese":
                self.source_lang.set("日文")
            elif current_source == "English":
                self.source_lang.set("英文")
            elif current_source == "Auto Detect":
                self.source_lang.set("自動偵測")
                
            if current_target == "Traditional Chinese":
                self.target_lang.set("繁體中文")
            elif current_target == "English":
                self.target_lang.set("英文")
            elif current_target == "Japanese":
                self.target_lang.set("日文")

    def create_widgets(self):
        # 按鈕框架
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)

        # 語言切換按鈕
        self.lang_button = ttk.Button(
            button_frame,
            text=self.get_text("switch_language"),
            command=self.switch_language
        )
        self.lang_button.pack(side=tk.LEFT, padx=5)

        # 檔案選擇按鈕
        self.file_button = ttk.Button(
            button_frame,
            text=self.get_text("select_files"),
            command=self.select_files
        )
        self.file_button.pack(side=tk.LEFT, padx=5)

        # 文件夾批量新增按鈕
        self.folder_button = ttk.Button(
            button_frame,
            text=self.get_text("select_folder"),
            command=self.select_folder
        )
        self.folder_button.pack(side=tk.LEFT, padx=5)

        # 檔案列表框架
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 檔案列表
        self.file_list = tk.Listbox(list_frame, width=70, height=10, selectmode=tk.SINGLE)
        self.file_list.pack(fill=tk.BOTH, expand=True)
        
        # 綁定 Del 鍵事件
        self.file_list.bind('<Delete>', self.delete_selected_file)
        
        # 添加滾動條
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_list.configure(yscrollcommand=scrollbar.set)

        # 語言選擇框架
        lang_frame = ttk.Frame(self)
        lang_frame.pack(pady=10)

        # 原文語言標籤和選擇框
        self.source_lang_label = ttk.Label(lang_frame, text=self.get_text("source_lang_label"))
        self.source_lang_label.grid(row=0, column=0)
        self.source_lang = ttk.Combobox(lang_frame, values=self.translations[self.current_language.get()]["source_lang_options"])
        self.source_lang.set(self.translations[self.current_language.get()]["source_lang_options"][0])  # 設置預設值
        self.source_lang.grid(row=0, column=1)

        # 目標語言標籤和選擇框
        self.target_lang_label = ttk.Label(lang_frame, text=self.get_text("target_lang_label"))
        self.target_lang_label.grid(row=0, column=2)
        self.target_lang = ttk.Combobox(lang_frame, values=self.translations[self.current_language.get()]["target_lang_options"])
        self.target_lang.set(self.translations[self.current_language.get()]["target_lang_options"][0])  # 設置預設值
        self.target_lang.grid(row=0, column=3)

        # 模型選擇框架
        model_frame = ttk.Frame(self)
        model_frame.pack(pady=10)

        # 模型選擇標籤和選擇框
        self.model_label = ttk.Label(model_frame, text=self.get_text("model_label"))
        self.model_label.grid(row=0, column=0)
        self.model_combo = ttk.Combobox(model_frame, values=self.get_model_list())
        self.model_combo.set("huihui_ai/aya-expanse-abliterated:latest")
        self.model_combo.grid(row=0, column=1)

        # 並行請求數標籤和選擇框
        self.parallel_label = ttk.Label(model_frame, text=self.get_text("parallel_label"))
        self.parallel_label.grid(row=0, column=2)
        self.parallel_requests = ttk.Combobox(model_frame, values=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "15", "20"])
        self.parallel_requests.set("10")
        self.parallel_requests.grid(row=0, column=3)

        # Checkbox 框架
        checkbox_frame = ttk.Frame(self)
        checkbox_frame.pack(pady=5)

        # 使用 grid 布局來實現自動換行
        # 設定每行最多顯示 2 個複選框
        max_columns = 2

        # 清理模式複選框
        self.clean_mode_check = ttk.Checkbutton(
            checkbox_frame,
            text=self.get_text("auto_clean"),
            variable=self.clean_mode_var
        )
        self.clean_mode_check.grid(row=0, column=0, padx=10, pady=2, sticky='w')

        # 調試模式複選框
        self.debug_mode_check = ttk.Checkbutton(
            checkbox_frame,
            text=self.get_text("debug_mode"),
            variable=self.debug_mode_var
        )
        self.debug_mode_check.grid(row=0, column=1, padx=10, pady=2, sticky='w')

        # 自動清理工作區複選框
        self.auto_clean_workspace_check = ttk.Checkbutton(
            checkbox_frame,
            text=self.get_text("clean_workspace"),
            variable=self.auto_clean_workspace_var
        )
        self.auto_clean_workspace_check.grid(row=1, column=0, padx=10, pady=2, sticky='w')

        # 取代原始檔案複選框
        self.replace_original_check = ttk.Checkbutton(
            checkbox_frame,
            text=self.get_text("replace_original"),
            variable=self.replace_original_var
        )
        self.replace_original_check.grid(row=1, column=1, padx=10, pady=2, sticky='w')

        # 配置 grid 的列和行權重，使其能夠自適應
        checkbox_frame.grid_columnconfigure(0, weight=1)
        checkbox_frame.grid_columnconfigure(1, weight=1)

        # 翻譯按鈕
        self.translate_button = ttk.Button(
            self,
            text=self.get_text("start_translation"),
            command=self.start_translation
        )
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

    def select_files(self):
        files = filedialog.askopenfilenames(filetypes=[("SRT files", "*.srt")])
        for file in files:
            self.file_list.insert(tk.END, file)

    def select_folder(self):
        """選擇文件夾並批量添加 SRT 檔案"""
        folder_path = filedialog.askdirectory(title="選擇包含 SRT 檔案的文件夾")
        if not folder_path:
            return

        # 計數器
        added_count = 0
        skipped_count = 0
        backup_count = 0

        # 遍歷文件夾中的所有檔案
        for root, dirs, files in os.walk(folder_path):
            # 跳過 backup 目錄
            if 'backup' in dirs:
                dirs.remove('backup')  # 這會讓 os.walk 跳過 backup 目錄
            
            # 檢查當前目錄是否為 backup 目錄
            if os.path.basename(root) == 'backup':
                backup_count += len([f for f in files if f.lower().endswith('.srt')])
                continue
                
            for file in files:
                if file.lower().endswith('.srt'):
                    # 跳過中文翻譯檔案
                    if file.lower().endswith('.zh_tw.srt'):
                        skipped_count += 1
                        continue
                    
                    full_path = os.path.join(root, file)
                    
                    # 檢查是否已在列表中
                    already_exists = False
                    for i in range(self.file_list.size()):
                        if self.file_list.get(i) == full_path:
                            already_exists = True
                            skipped_count += 1
                            break
                    
                    if not already_exists:
                        self.file_list.insert(tk.END, full_path)
                        added_count += 1

        # 顯示結果
        message = f"已添加 {added_count} 個 SRT 檔案"
        if skipped_count > 0 or backup_count > 0:
            message += f"\n已跳過 {skipped_count} 個檔案（包含已翻譯檔案或重複檔案）"
            if backup_count > 0:
                message += f"\n已跳過 {backup_count} 個備份目錄中的檔案"
        
        if added_count > 0:
            messagebox.showinfo("完成", message)
        else:
            messagebox.showwarning("提示", "未找到可添加的 SRT 檔案")

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
            messagebox.showwarning(
                self.get_text("no_files"),
                self.get_text("no_files_message")
            )
            return

        # 如果選擇取代原始檔案，詢問使用者確認
        if self.replace_original_var.get():
            if not messagebox.askyesno(
                self.get_text("confirm"),
                self.get_text("replace_warning")
            ):
                return

        # 如果開啟了清理模式，先清理檔案
        if self.clean_mode_var.get():
            self.status_label.config(text=self.get_text("cleaning"))
            self.update_idletasks()
            
            total_cleaned = 0
            total_subtitles = 0
            
            for i in range(self.file_list.size()):
                input_file = self.file_list.get(i)
                try:
                    # 只在取代原始檔案模式下創建備份
                    if self.replace_original_var.get():
                        backup_path = os.path.join(os.path.dirname(input_file), 'backup')
                        self.ensure_backup_dir(backup_path)
                        backup_file = os.path.join(backup_path, os.path.basename(input_file))
                        shutil.copy2(input_file, backup_file)
                    
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
                    self.status_label.config(
                        text=self.get_text("cleaning_progress").format(
                            i+1,
                            self.file_list.size(),
                            progress,
                            total_cleaned,
                            total_subtitles
                        )
                    )
                    self.update_idletasks()
                    
                except Exception as e:
                    messagebox.showerror(
                        self.get_text("error"),
                        str(e)
                    )
                    return

            self.status_label.config(
                text=self.get_text("cleaning_complete").format(
                    total_cleaned,
                    total_subtitles
                )
            )
            self.update_idletasks()

        # 重置進度條
        self.progress_bar['value'] = 0
        total_files = self.file_list.size()
        
        # 開始翻譯
        for i in range(total_files):
            file_path = self.file_list.get(i)
            thread = TranslationThread(
                file_path, 
                self.source_lang.get(), 
                self.target_lang.get(), 
                self.model_combo.get(),
                self.parallel_requests.get(),
                self.update_progress,
                self.file_translated,
                self.debug_mode_var.get(),
                self.replace_original_var.get()
            )
            thread.set_app(self)
            thread.start()

        self.status_label.config(
            text=self.get_text("translating").format(total_files)
        )

    def update_progress(self, current, total, extra_data=None):
        """更新進度"""
        if extra_data and extra_data.get("type") == "file_conflict":
            # 在主線程中顯示對話框
            app = extra_data.get("app")
            if app:
                result = app.show_countdown_dialog(
                    f"檔案 {extra_data['path']} 已存在。\n請選擇處理方式：\n\n'覆蓋' = 覆蓋現有檔案\n'重新命名' = 自動重新命名\n'跳過' = 跳過此檔案",
                    countdown=5
                )
                
                # 將結果發送回翻譯線程
                extra_data["queue"].put(result)
            return
            
        # 正常的進度更新
        if current >= 0 and total >= 0:
            percentage = int(current / total * 100)
            self.progress_bar['value'] = percentage
            self.status_label.config(
                text=self.get_text("translation_progress").format(
                    current,
                    total,
                    percentage
                )
            )
            self.update_idletasks()

    def file_translated(self, message):
        """處理檔案翻譯完成的回調"""
        current_text = self.status_label.cget("text")
        self.status_label.config(text=f"{current_text}\n{message}")
        
        # 檢查是否所有檔案都已翻譯完成
        if "翻譯完成" in message:
            # 從檔案列表中移除已翻譯的檔案
            if self.auto_clean_workspace_var.get():
                for i in range(self.file_list.size()):
                    if os.path.basename(self.file_list.get(i)) in message:
                        self.file_list.delete(i)
                        break
            
            # 如果檔案列表為空且啟用了自動清理，顯示完成訊息
            if self.file_list.size() == 0 and self.auto_clean_workspace_var.get():
                self.status_label.config(text=self.get_text("workspace_cleaned"))
                self.progress_bar['value'] = 0
                messagebox.showinfo(
                    self.get_text("confirm"),
                    self.get_text("workspace_cleaned")
                )
            # 如果檔案列表不為空或未啟用自動清理，只顯示翻譯完成訊息
            elif not self.auto_clean_workspace_var.get():
                self.status_label.config(text=self.get_text("all_complete"))
                self.progress_bar['value'] = 0
                messagebox.showinfo(
                    self.get_text("confirm"),
                    self.get_text("all_complete")
                )

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

    def show_countdown_dialog(self, message, countdown=5):
        """顯示帶有倒計時的對話框"""
        # 創建新視窗
        countdown_window = tk.Toplevel(self)
        countdown_window.title("檔案已存在")
        countdown_window.geometry("400x200")
        countdown_window.transient(self)  # 設置為主視窗的子視窗
        countdown_window.grab_set()  # 模態視窗
        countdown_window.resizable(False, False)  # 禁止調整視窗大小
        
        # 保存視窗引用
        self.countdown_window = countdown_window
        self.dialog_result = None

        # 創建主框架
        main_frame = ttk.Frame(countdown_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 添加訊息標籤
        message_label = ttk.Label(main_frame, text=message, wraplength=350, justify="center")
        message_label.pack(pady=(0, 10))
        
        # 添加倒計時標籤
        self.countdown_label = ttk.Label(main_frame, text=f"{countdown} 秒後自動重新命名", font=("Arial", 10, "bold"))
        self.countdown_label.pack(pady=(0, 20))
        
        # 添加按鈕框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(0, 10))
        
        # 設置按鈕樣式
        style = ttk.Style()
        style.configure("Action.TButton", padding=5)
        
        # 添加按鈕
        overwrite_btn = ttk.Button(
            button_frame, 
            text="覆蓋", 
            style="Action.TButton",
            command=lambda: self.set_dialog_result("overwrite")
        )
        overwrite_btn.pack(side=tk.LEFT, padx=5)
        
        rename_btn = ttk.Button(
            button_frame, 
            text="重新命名", 
            style="Action.TButton",
            command=lambda: self.set_dialog_result("rename")
        )
        rename_btn.pack(side=tk.LEFT, padx=5)
        
        skip_btn = ttk.Button(
            button_frame, 
            text="跳過", 
            style="Action.TButton",
            command=lambda: self.set_dialog_result("skip")
        )
        skip_btn.pack(side=tk.LEFT, padx=5)
        
        # 開始倒計時
        def update_countdown():
            nonlocal countdown
            if countdown > 0 and self.dialog_result is None:
                countdown -= 1
                self.countdown_label.config(text=f"{countdown} 秒後自動重新命名")
                countdown_window.after(1000, update_countdown)
            elif self.dialog_result is None:
                self.set_dialog_result("rename")
        
        # 置中顯示視窗
        countdown_window.update_idletasks()
        width = countdown_window.winfo_width()
        height = countdown_window.winfo_height()
        x = (countdown_window.winfo_screenwidth() // 2) - (width // 2)
        y = (countdown_window.winfo_screenheight() // 2) - (height // 2)
        countdown_window.geometry(f"{width}x{height}+{x}+{y}")
        
        countdown_window.after(1000, update_countdown)
        countdown_window.wait_window()
        return self.dialog_result

    def set_dialog_result(self, result):
        """設置對話框結果並關閉視窗"""
        self.dialog_result = result
        if self.countdown_window:
            self.countdown_window.destroy()
            self.countdown_window = None

    def delete_selected_file(self, event=None):
        """刪除選中的檔案"""
        try:
            selected = self.file_list.curselection()
            if selected:
                self.file_list.delete(selected)
                self.status_label.config(text=self.get_text("file_removed"))
        except Exception as e:
            messagebox.showerror(
                self.get_text("error"),
                self.get_text("error_message").format(str(e))
            )

if __name__ == "__main__":
    app = App()
    app.mainloop()