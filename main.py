"""
Entry point — run with: python main.py
Then open http://localhost:8080
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.api:app", host="127.0.0.1", port=8080, reload=False, log_level="warning")
