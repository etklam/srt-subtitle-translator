import os
import re
import shutil
import pysrt

def ensure_backup_dir(backup_path):
    """確保備份目錄存在"""
    if not os.path.exists(backup_path):
        os.makedirs(backup_path)

def clean_srt_file(input_file, create_backup=False):
    """清理 SRT 檔案，移除不需要的字幕，重新排序字幕編號"""
    result = {
        "cleaned": 0,
        "total": 0
    }
    
    try:
        # 如果需要創建備份
        if create_backup:
            backup_path = os.path.join(os.path.dirname(input_file), 'backup')
            ensure_backup_dir(backup_path)
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
                    result["total"] += 1
                    if len(current_subtitle) >= 3 and not re.match(r'^\(\s*[^)]*\s*\)$', current_subtitle[2]):
                        current_subtitle[0] = str(subtitle_number)
                        new_lines.extend(current_subtitle)
                        new_lines.append('')
                        subtitle_number += 1
                        result["cleaned"] += 1
                    current_subtitle = []
            else:
                current_subtitle.append(line)
        
        # 處理最後一個字幕
        if current_subtitle:
            result["total"] += 1
            if not re.match(r'^\(\s*[^)]*\s*\)$', current_subtitle[2]):
                current_subtitle[0] = str(subtitle_number)
                new_lines.extend(current_subtitle)
                result["cleaned"] += 1
        
        # 寫回原始檔案
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        
        return result
        
    except Exception as e:
        raise Exception(f"處理檔案時發生錯誤: {str(e)}")

def get_language_suffix(language):
    """根據語言名稱獲取檔案後綴"""
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
        "馬來文": ".ms",
        "Traditional Chinese": ".zh_tw", 
        "English": ".en", 
        "Japanese": ".jp", 
        "Korean": ".ko", 
        "French": ".fr", 
        "German": ".de", 
        "Spanish": ".es", 
        "Italian": ".it", 
        "Portuguese": ".pt", 
        "Russian": ".ru", 
        "Arabic": ".ar", 
        "Hindi": ".hi", 
        "Indonesian": ".id", 
        "Vietnamese": ".vi", 
        "Thai": ".th", 
        "Malay": ".ms"
    }
    return lang_suffix.get(language, ".unknown")

def get_output_path(file_path, target_lang, replace_original=False):
    """獲取翻譯後的輸出路徑"""
    # 如果選擇取代原始檔案，直接返回原始檔案路徑
    if replace_original:
        return file_path

    # 獲取原始檔案的目錄和檔名
    dir_name, file_name = os.path.split(file_path)
    name, ext = os.path.splitext(file_name)
    
    # 在原始檔案的相同目錄下創建新檔案
    lang_suffix = get_language_suffix(target_lang)
    return os.path.join(dir_name, f"{name}{lang_suffix}{ext}")
