import threading
import asyncio
import os
import json
import urllib.request
import pysrt
from queue import Queue

from src.utils.file_utils import ensure_backup_dir, get_output_path

class TranslationThread(threading.Thread):
    def __init__(self, file_path, source_lang, target_lang, model_name, parallel_requests, progress_callback, complete_callback, debug_mode=False, replace_original=False, use_alt_prompt=False):
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
        self.use_alt_prompt = use_alt_prompt

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
                ensure_backup_dir(backup_path)
                backup_file = os.path.join(backup_path, os.path.basename(self.file_path))
                import shutil
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
        system_prompt = self._get_system_prompt()
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
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

    def _get_system_prompt(self):
        import json
        import os

        # Default prompt to use if JSON loading fails
        default_fallback_prompt = """You are a professional translator請嚴格遵守以下規則：1. 只輸出翻譯後的文本，不要有任何其他回應。2. 根據提供的上下文（前後五句字幕）並考量影片來優化翻譯結果，確保流暢且符合對話邏輯。2. 保持原文的語氣和表達方式3. 如果看到省略號(...)，保留在譯文中4. 保留原文中的標點符號風格5. 不要添加任何解釋或註釋6. 不要改變原文的格式7. 如果遇到不確定的內容，根據上下文合理推測8. 禁止輸出任何非翻譯內容9. 禁止解釋或評論原文內容範例輸入："I love you..."正確輸出："我愛你..."Incorrect output:"翻譯：我愛你...""這句話的意思是：我愛你...""我愛你（這是表達愛意）...""我可以幫你翻譯，這句話的意思是，我愛你（這是表達愛意）...""你好！我可以幫你翻譯。以下是翻譯結果：「我愛你...」"我不能幫你翻譯這句話""您好！以下是翻譯結果：「我愛你...」""您好！我可以協助您翻譯。以下是翻譯結果：「我愛你...」""您要我翻譯什麼內容？請提供需要翻譯的文本，我將嚴格遵守您的要求，只輸出翻譯後的結果。""將以下文本翻譯成繁體中文：「我愛你...」"Translation: I love you...""This means: I love you...""I love you (this is an expression of love)...""I can help you translate, this means: I love you (this is an expression of love)...""Hello! I can help you translate. Here is the translation result: 'I love you...'""I cannot translate this sentence""Hello! Here is the translation result: 'I love you...'""Hello! I can assist you with translation. Here is the translation result: 'I love you...'""Please provide the text you want to translate, and I will strictly follow your requirements and only output the translation result.""Translate the following text to Traditional Chinese: 'I love you...'"""

        try:
            # Load prompts from JSON file
            prompts_path = os.path.join(os.path.dirname(__file__), 'prompts.json')
            with open(prompts_path, 'r', encoding='utf-8') as f:
                prompts = json.load(f)
        
            if self.use_alt_prompt:
                # Use alt_prompt if available, otherwise fall back to default_prompt
                return prompts.get('alt_prompt', prompts.get('default_prompt', default_fallback_prompt))
            else:
                return prompts.get('default_prompt', default_fallback_prompt)
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            # If any error occurs (file not found, invalid JSON, or missing key),
            # log the error and use the fallback prompt
            if self.debug_mode:
                print(f"Error loading prompts: {str(e)}. Using fallback prompt.")
        
            return default_fallback_prompt


    def get_output_path(self):
        """獲取輸出路徑"""
        base_path = get_output_path(self.file_path, self.target_lang, self.replace_original)
        
        # 檢查檔案是否存在
        if os.path.exists(base_path) and not self.replace_original:
            # 發送訊息到主線程處理檔案衝突
            response = self.handle_file_conflict(base_path)
            if response == "rename":
                # 自動重新命名，加上數字後綴
                dir_name, file_name = os.path.split(self.file_path)
                name, ext = os.path.splitext(file_name)
                from src.utils.file_utils import get_language_suffix
                lang_suffix = get_language_suffix(self.target_lang)
                
                counter = 1
                while True:
                    new_path = os.path.join(dir_name, f"{name}{lang_suffix}_{counter}{ext}")
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
