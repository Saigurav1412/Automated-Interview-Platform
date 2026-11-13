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
        # Wait for a longer pause before treating the candidate's turn as finished,
        # so thinking pauses mid-answer don't trigger the next question (default 0.5s)
        min_endpointing_delay=1.5,
    )

    speech_state = {
        "last_user_speech": time.time(),
        "last_agent_speech_end": 0.0,
        "agent_busy": False,
    }

    @session.on("agent_state_changed")
    def on_agent_state(ev):
        # The stage manager must not close the interview while the agent is
        # generating or speaking a reply (e.g. a new question after "skip")
        speech_state["agent_busy"] = ev.new_state in ("thinking", "speaking")
        if ev.old_state == "speaking" and ev.new_state != "speaking":
            speech_state["last_agent_speech_end"] = time.time()

    @session.on("user_input_transcribed")
    def on_user_speech(ev):
        speech_state["last_user_speech"] = time.time()
        if ev.is_final and agent.current_stage == InterviewStage.INTRO:
            agent.intro_text += " " + ev.transcript

    # 4. Start
    await session.start(agent=agent, room=ctx.room)

    # 5. Run the Stage Manager (Imported from agents.py)
    # DO NOT define stage_manager() here. Use the imported one.
    stage_task = asyncio.create_task(run_stage_manager(session, agent, speech_state))

    async def _stop_stage_manager():
        stage_task.cancel()

    ctx.add_shutdown_callback(_stop_stage_manager)

    # 6. First Greeting
    await asyncio.sleep(1)
    await session.generate_reply(instructions="Say hello and ask for my name and role.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))