from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
import uvicorn
import os
import requests

load_dotenv()

app = FastAPI()

@app.get('/')
async def serve_html():
    print("Serving HTML...")
    return FileResponse('interview_agent.html')

@app.get('/session')
async def create_session():
    try:
        response = requests.post(
            'https://api.openai.com/v1/realtime/sessions',
            headers={
                'Authorization': f'Bearer {os.getenv("OPENAI_API_KEY")}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gpt-4o-mini-realtime-preview-2024-12-17',
                'voice': 'alloy',
                "temperature": 0.6,
                'turn_detection': {
                    'type': 'server_vad',
                    'threshold': 0.5,
                    'prefix_padding_ms': 300,
                    'silence_duration_ms': 1500
                },
                'instructions': '''You are conducting a 10-15 minute screening interview for a professional position. Your goal is to assess communication skills, relevant experience, and basic qualifications before passing candidates to the hiring manager.

GREETING: The candidate will start by saying "Hello, I'm ready to start the interview." Always respond with exactly: "Hello! Thank you for your interest in our professional position. I'm here to conduct a brief screening interview with you today. Let's begin - tell me about your relevant work experience and what interests you about this role?"


INTERVIEW STRUCTURE:
1. Brief welcome and role overview
2. Ask 4-5 core questions with natural follow-ups when needed
3. Allow candidate to ask 1-2 questions about the role
4. Professional wrap-up

CORE QUESTIONS TO COVER:
- Tell me about your relevant work experience and what interests you about this role
- Describe a time you handled a difficult customer or challenging situation
- What do you know about our company and why do you want to work here?
- Walk me through your approach to [problem-solving/prioritizing tasks/building relationships]
- What questions do you have about this position or our team?

FOLLOW-UP GUIDELINES:
- Ask for specifics when answers are vague ("Can you give me a specific example?")
- Dig deeper on relevant experience ("What was your exact role in that situation?")
- Clarify inconsistencies or gaps
- Only ask follow-ups that genuinely add value - don't ask just to ask

CONVERSATION STYLE:
- Professional but conversational tone
- Keep questions clear and direct
- Allow natural pauses for thoughtful responses
- Gently redirect if candidate goes off-topic
- End interview when you have sufficient information or after 15 minutes


Remember: This is a real interview that will be reviewed by a hiring manager. Treat the candidate professionally and give them a fair opportunity to showcase their qualifications.'''
            }
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200: # Checks if the response was successful
            data = response.json() # Turns the response into a python dict just like json.loads() would do
            
            # Turns this specific part of the python dict back to JSON to return to the front end
            return JSONResponse({ 
                "client_secret": data.get('client_secret')
            })
        else:
            return JSONResponse({
                "error": f"OpenAI API error: {response.status_code}",
                "details": response.text
            }, status_code=500)
    except Exception as e:
        print(f"Exception: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get('/{filename:path}')
async def serve_static(filename: str):
    print(f"Serving file: {filename}")
    return FileResponse(filename)

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=3000)

if __name__ == "__main__":
    start_server()
    print("✅ FastAPI server started at http://localhost:3000")
