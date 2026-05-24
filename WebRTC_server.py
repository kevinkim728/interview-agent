from fastapi import FastAPI
from fastapi.responses import FileResponse
from dotenv import load_dotenv
import uvicorn

load_dotenv()

app = FastAPI()

@app.get('/')
async def serve_html():
    print("Serving HTML...")
    return FileResponse('interview_agent.html')

@app.get('/{filename:path}')
async def serve_static(filename: str):
    print(f"Serving file: {filename}")
    return FileResponse(filename)

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=3000)

if __name__ == "__main__":
    start_server()
    print("✅ FastAPI server started at http://localhost:3000")
