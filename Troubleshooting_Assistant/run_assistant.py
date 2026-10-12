"""Start the integrated local application."""
import os
from pathlib import Path
import uvicorn

if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)
    print("Assistant: http://127.0.0.1:8000/assistant", flush=True)
    uvicorn.run("app.integrated:app", host="127.0.0.1", port=8000)
