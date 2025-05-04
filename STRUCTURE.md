# SRT Subtitle Translator - Project Structure

This document outlines the modular structure of the SRT Subtitle Translator application after refactoring.

## Directory Structure

```
srt-subtitle-translator-enhanced/
├── main.py                 # Main entry point
├── src/                    # Source code package
│   ├── __init__.py         # Package marker
│   ├── main.py             # Application initialization 
│   ├── gui/                # GUI components
│   │   ├── __init__.py     # Package marker
│   │   └── app.py          # Main application window
│   ├── translation/        # Translation functionality
│   │   ├── __init__.py     # Package marker
│   │   └── translation_thread.py  # Background translation thread
│   └── utils/              # Utility functions
│       ├── __init__.py     # Package marker
│       └── file_utils.py   # File handling utilities
```

## Module Functionality

### main.py
The root main.py file serves as a simple entry point that imports and runs the actual application from the src package.

### src/main.py
Initializes the application and contains the `main()` function that creates and runs the application window.

### src/gui/app.py
Contains the `App` class which defines the user interface, including:
- File selection and listing
- Language selection
- Model selection
- Translation options
- Progress display
- File conflict handling

### src/translation/translation_thread.py
Contains the `TranslationThread` class which:
- Runs translation in a background thread
- Connects to the Ollama API
- Processes subtitle files
- Handles output file naming and conflicts

### src/utils/file_utils.py
Contains utility functions for:
- File backup
- SRT file cleaning and processing
- Output path generation
- Language suffix handling

## Benefits of Modularization

1. **Improved maintainability**: Each module has a clear, focused responsibility
2. **Better organization**: Related code is grouped together
3. **Easier navigation**: Simpler to find specific functionality
4. **Reduced complexity**: Smaller files with clearer purpose
5. **Better reusability**: Functions and classes can be easily imported where needed
6. **Easier testing**: Components can be tested independently
7. **Cleaner architecture**: Clear separation of UI, business logic, and utilities
