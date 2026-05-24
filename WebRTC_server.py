from fastapi import FastAPI
from dotenv import load_dotenv
import uvicorn

load_dotenv()

app = FastAPI()

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=3000)

if __name__ == "__main__":
    start_server()
    print("✅ FastAPI server started at http://localhost:3000")
