import sys
import os

# Set Ollama parallel requests
os.environ['OLLAMA_NUM_PARALLEL'] = '5'

# Import the application from our new module structure
from src.main import main

if __name__ == "__main__":
    # Execute the main function from src.main
    sys.exit(main())
