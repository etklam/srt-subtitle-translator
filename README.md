# SRT Subtitle Translator

A powerful SRT subtitle translation tool based on Ollama, supporting translation between multiple languages with various useful features.

## Features

### Core Features
- Batch translation of SRT subtitle files
- Drag and drop file support
- Bulk folder import
- Smart file backup (only when replacing original files)
- Multiple translation model support
- Multi-threaded parallel translation (up to 20 parallel requests)

### Translation Options
- Support for Japanese, English, and Traditional Chinese translations
- Source and target language selection
- Automatic source language detection

### Advanced Features
- Auto-clean before translation (removes invalid subtitles)
- Direct original file replacement mode (with automatic backup)
- Automatic file conflict handling (overwrite/rename/skip)
- Workspace auto-cleanup after translation
- Debug mode support

## System Requirements

- Python 3.6 or higher
- Ollama service running locally (default port: 11434)
- tkinterdnd2 recommended for drag-and-drop support

## Installation

1. Install required Python packages:
```bash
pip install -r requirements.txt
```

2. Ensure Ollama service is running:
```bash
ollama serve
```

3. Download the required translation model:
```bash
ollama pull huihui_ai/aya-expanse-abliterated
```

## Usage Guide

### Basic Operations
1. Run the program:
```bash
python main.py
```

2. Add files using one of these methods:
   - Click "Select SRT Files" button
   - Drag and drop files into the window
   - Use "Add Folder" feature

3. Select translation settings:
   - Choose source language (Japanese/English/Auto Detect)
   - Choose target language (Traditional Chinese/English/Japanese)
   - Select translation model
   - Set parallel requests (1-20)

4. Click "Start Translation" to begin processing

### Advanced Settings

#### File Processing Options
- [Auto Clean Before Translation]: Automatically remove invalid subtitle lines
- [Replace Original File]: Directly overwrite original files (with automatic backup)
- [Clean Workspace After Translation]: Auto-clear file list after completion
- [Debug Mode]: Display detailed translation process information

#### File Conflict Handling
When target file already exists, system provides three options:
- Overwrite: Replace existing file
- Rename: Automatically add numeric suffix
- Skip: Keep existing file unchanged

## Important Notes

1. Backup Information
   - Original files are backed up only when using "Replace Original File" mode
   - Backups are stored in a 'backup' folder in the same directory

2. Performance Considerations
   - Adjust parallel requests based on system performance
   - Default value is 10, adjustable from 1-20

3. File Naming Convention
   - Default: Adds language suffix to filename (e.g., .zh_tw.srt)
   - Original filename preserved in replacement mode

## Troubleshooting

1. If translation fails:
   - Verify Ollama service is running
   - Check network connection
   - Confirm selected model is installed

2. If drag-and-drop doesn't work:
   - Verify tkinterdnd2 is installed
   - Reinstall program dependencies

## Technical Support

If you encounter issues:
1. Check common problems section
2. Verify you're using the latest version
3. Provide detailed error information and steps to reproduce

## Language Support

The application interface supports:
- Traditional Chinese
- English

You can switch between languages using the language toggle button at the top of the window.

## License

This program is open-source software, released under the MIT License. 