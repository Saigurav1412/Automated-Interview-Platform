import logging
import time
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

from livekit.agents import AutoSubscribe, WorkerOptions, cli, JobContext
from livekit.agents.voice import AgentSession
from livekit.plugins import deepgram, google, silero

# IMPORTS
from stages import InterviewStage
from prompts import Stage_PROMPTS
from utils import parse_resume
from agents import InterviewAgent, run_stage_manager # <--- IMPORT THE LOGIC

# Load Env correctly
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # 1. Resume
    resume_path = os.getenv("GUI_RESUME_PATH", "resume.pdf")
    resume_text = parse_resume(resume_path)
    
    # 2. Initialize Agent
    agent = InterviewAgent(resume_text=resume_text)

    # 3. Session
    session = AgentSession(
        stt=deepgram.STT(),
        llm=google.LLM(model="models/gemini-2.5-flash"),
        tts=deepgram.TTS(),
        vad=silero.VAD.load(),
    )

    speech_state = {"last_user_speech": time.time()}

    @session.on("user_speech_committed")
    def on_user_speech(msg):
        speech_state["last_user_speech"] = time.time()
        if agent.current_stage == InterviewStage.INTRO:
            agent.intro_text += " " + msg.content

    # 4. Start
    await session.start(agent=agent, room=ctx.room)

    # 5. Run the Stage Manager (Imported from agents.py)
    # DO NOT define stage_manager() here. Use the imported one.
    asyncio.create_task(run_stage_manager(session, agent, speech_state))

    # 6. First Greeting
    await asyncio.sleep(1)
    await session.generate_reply(instructions="Say hello and ask for my name and role.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))