import os
import sys
import tkinter as tk

# 添加當前目錄到 PATH，以便可以導入模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 導入自定義模組
from src.gui.app import App

def main():
    """程式主入口點"""
    app = App()
    app.mainloop()
    return 0

if __name__ == "__main__":
    sys.exit(main())
