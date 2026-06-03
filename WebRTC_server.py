from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
import uvicorn
import os
import requests
import time
from fastapi import UploadFile, File
import subprocess
import whisper
from pyannote.audio import Pipeline
from job_config import JOB_DESCRIPTION, JOB_TITLE
from interview_analyzer import analyze_interview

load_dotenv()

whisper_model = whisper.load_model("base")

print("Loading speaker diarization model...")
diarization_pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    token=os.getenv("HUGGINGFACE_TOKEN")
)
print("✅ Diarization model loaded")

MODEL = 'gpt-realtime-2'

INTERVIEW_PROMPT = f'''JOB DESCRIPTION:
{JOB_DESCRIPTION}

You are conducting a 10-15 minute screening interview for a professional position. Your goal is to assess communication skills, relevant experience, and basic qualifications before passing candidates to the hiring manager.

GREETING: The candidate will start by saying "Hello, I'm ready to start the interview." Always respond with exactly: "Hello! Thank you for your interest in our {JOB_TITLE} position. I'm here to conduct a brief screening interview with you today. Let's begin - tell me about your relevant work experience and what interests you about this role?"


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

app = FastAPI()

@app.get('/')
async def serve_html():
    print("Serving HTML...")
    return FileResponse('interview_agent.html')

@app.get('/session')
async def create_session():
    try:
        response = requests.post(
            'https://api.openai.com/v1/realtime/client_secrets',
            headers={
                'Authorization': f'Bearer {os.getenv("OPENAI_API_KEY")}',
                'Content-Type': 'application/json'
            },
            json={
                'session': {
                    'type': 'realtime',
                    'model': MODEL,
                    'instructions': INTERVIEW_PROMPT,
                    'audio': {
                        'input': {
                            'turn_detection': {
                                'type': 'semantic_vad',
                                'eagerness': 'low'
                            },
                            'noise_reduction': {
                                'type': 'far_field'
                            }
                        },
                        'output': {
                            'voice': 'marin'
                        }
                    },
                    'tracing': 'auto'
                }
            }
        )

        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200:
            data = response.json()
            return JSONResponse({
                "client_secret": data.get('value')
            })
        else:
            return JSONResponse({
                "error": f"OpenAI API error: {response.status_code}",
                "details": response.text
            }, status_code=500)
    except Exception as e:
        print(f"Exception: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

def create_labeled_transcript(whisper_result, diarization):
    segments = whisper_result["segments"]
    labeled_parts = []

    interviewer = None
    for turn, _, spk in diarization.speaker_diarization.itertracks(yield_label=True): # turn gets the time someone spoke, spk gets the speaker label
        interviewer = spk # gets the first speaker and assigns it to a the interviewer variable
        break

    # Checks to see if the first person said less than 20 words. If it did then change the who is labeled the interviewer
    if segments:
        first_text = segments[0]["text"].strip()
        if len(first_text) < 20:
            for turn, _, spk in diarization.speaker_diarization.itertracks(yield_label=True): # Loop to see if the first speaker was the interviewr
                if spk != interviewer:
                    interviewer = spk
                    break

    for segment in segments:
        start_time = segment["start"]
        text = segment["text"]

        speaker = "INTERVIEWER" if spk == interviewer else "CANDIDATE"
        for turn, _, spk in diarization.speaker_diarization.itertracks(yield_label=True):
            if turn.start <= start_time <= turn.end:
                speaker = "INTERVIEWER" if spk == interviewer else "CANDIDATE"
                break

        labeled_parts.append(f"{speaker}: {text}")

    return "\n".join(labeled_parts)

def convert_webm_to_wav(webm_path):
    wav_path = webm_path.replace('.webm', '.wav')

    try:
        subprocess.run([
            'ffmpeg', '-i', webm_path,
            '-ar', '16000',
            '-ac', '1',
            '-y',
            wav_path
        ], check=True, capture_output=True, text=True)

        return wav_path
    except subprocess.CalledProcessError as e:
        raise Exception(f"FFmpeg conversion failed: {e.stderr}")
    except FileNotFoundError:
        raise Exception("FFmpeg not found. Please install FFmpeg on your system.")

@app.post('/save-interview')
async def save_interview(audio: UploadFile = File(...)):
    try:
        timestamp = int(time.time())
        webm_filename = f"interview_{timestamp}.webm"
        webm_path = os.path.join('interviews', webm_filename)

        os.makedirs('interviews', exist_ok=True)

        contents = await audio.read()
        with open(webm_path, 'wb') as f:
            f.write(contents)
        print(f"📁 WebM file saved: {webm_filename}")

        print("🔄 Converting WebM to WAV...")
        wav_path = convert_webm_to_wav(webm_path) 
        wav_filename = os.path.basename(wav_path)
        print(f"✅ Conversion complete: {wav_filename}")

        print("🎯 Starting transcription...")
        result = whisper_model.transcribe(wav_path)
        print("✅ Transcription complete")

        print("🎯 Starting speaker diarization...")
        diarization = diarization_pipeline(wav_path)
        labeled_transcript = create_labeled_transcript(result, diarization)
        print("✅ Speaker diarization complete")

        labeled_transcript_filename = f"interview_{timestamp}_labeled.txt"
        labeled_transcript_path = os.path.join('interviews', labeled_transcript_filename)
        with open(labeled_transcript_path, 'w') as f:
            f.write(labeled_transcript)


        print("🧠 Starting interview analysis...")
        analysis = await analyze_interview(labeled_transcript)
        print("✅ Analysis complete")

        report_filename = f"interview_{timestamp}_report.txt"
        report_path = os.path.join('interviews', report_filename)

        report = f"""
INTERVIEW ANALYSIS REPORT
========================
Timestamp: {timestamp}

RECOMMENDATION: {analysis.recommendation}

SCORES:
- Communication: {analysis.communication_score:.1f}/1.0
- Engagement: {analysis.engagement_score:.1f}/1.0
- Specificity: {analysis.specificity_score:.1f}/1.0
- Qualification: {analysis.qualification_score:.1f}/1.0

SCORE BREAKDOWN:
{analysis.score_breakdown}

HIGHLIGHTS:
{chr(10).join(f"• {h}" for h in analysis.highlights)}

CONCERNS:
{chr(10).join(f"⚠️ {c}" for c in analysis.concerns)}

RED FLAGS:
{chr(10).join(f"🚨 {flag}" for flag in analysis.red_flags)}

SUMMARY:
{analysis.summary}
        """

        with open(report_path, 'w') as f:
            f.write(report)

        if os.path.exists(webm_path):
            os.remove(webm_path)
            print(f"✅ Removed WebM file: {webm_filename}")

        return JSONResponse({
            "success": True,
            "audio_saved": webm_filename,
            "wav_created": wav_filename,
            "transcript_saved": labeled_transcript_filename,
            "report_saved": report_filename,
            "transcript": labeled_transcript,
            "analysis": analysis.model_dump(),
            "message": "Interview saved, transcribed, diarized, and analyzed"
        })

    except Exception as e:
        print(f"❌ Error in save_interview: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)

    

@app.get('/{filename:path}')
async def serve_static(filename: str):
    if not os.path.exists(filename):
        return JSONResponse({"error": "Not found"}, status_code=404)
    print(f"Serving file: {filename}")
    return FileResponse(filename)

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=3000)

if __name__ == "__main__":
    start_server()
    print("✅ FastAPI server started at http://localhost:3000")
