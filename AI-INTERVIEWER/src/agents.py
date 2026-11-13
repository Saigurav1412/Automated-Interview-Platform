import os
import re
import time
import asyncio
import logging
from livekit.agents.voice import Agent, AgentSession
from stages import InterviewStage
from prompts import Stage_PROMPTS, TRANSITION_PHRASES, PERSONA_OVERRIDES

class InterviewAgent(Agent):
    def __init__(self, resume_text=None):
        super().__init__(instructions=Stage_PROMPTS[InterviewStage.INTRO])
        self.resume_text = resume_text
        self.current_stage = InterviewStage.INTRO
        self.stage_start_time = time.time()
        self.intro_text = ""

    async def update_role(self, mode):
        logging.info(f"--- SWITCHING PERSONA TO: {mode.upper()} ---")

        # 1. Select the correct brain
        base_prompt = PERSONA_OVERRIDES.get(mode, PERSONA_OVERRIDES["hr"])

        # 2. Add the Resume (if exists)
        context = ""
        if self.resume_text:
            context = f"\n\nCANDIDATE RESUME:\n{self.resume_text}"

        # 3. Add the STRICT RULES (prevents repeating/long answers)
        rules = (
            "\n\nRULES:"
            "\n- Ask exactly ONE question at a time."
            "\n- Wait for the user to answer."
            "\n- Keep responses short (1 sentence)."
        )

        # 4. Update the Agent's instructions dynamically
        await self.update_instructions(f"{base_prompt}{context}{rules}")

# Word-boundary patterns so e.g. "hr" doesn't match "three" and "code" doesn't match "decode"
ROLE_PATTERNS = [
    ("technical", re.compile(r"\b(developers?|engineer(s|ing)?|python|tech(nical)?|cod(e|er|ers|ing))\b")),
    ("sales", re.compile(r"\b(sales|marketing|business|accounts?)\b")),
    ("hr", re.compile(r"\b(hr|recruiters?|managers?|human resources)\b")),
]

def detect_role(text):
    text = (text or "").lower()
    for role, pattern in ROLE_PATTERNS:
        if pattern.search(text):
            return role
    return None

async def run_stage_manager(
    session: AgentSession,
    agent: InterviewAgent,
    speech_state: dict,
    poll_interval: float = 2.0,
    intro_timeout: float | None = None,
    interview_seconds: float | None = None,
    silence_seconds: float = 3.0,
):
    """
    Background task that monitors the conversation.
    """
    if intro_timeout is None:
        intro_timeout = float(os.getenv("INTRO_TIMEOUT_SECONDS", "45"))
    if interview_seconds is None:
        interview_seconds = float(os.getenv("INTERVIEW_SECONDS", "600"))

    logging.info("--- STAGE MANAGER RUNNING ---")

    while agent.current_stage != InterviewStage.CLOSING:
        await asyncio.sleep(poll_interval)
        try:
            now = time.time()
            elapsed = now - agent.stage_start_time

            # LOGIC: Switch from Intro -> Experience
            if agent.current_stage == InterviewStage.INTRO:
                role = detect_role(agent.intro_text)

                # After the timeout, fall back to the resume, then to HR
                if not role and elapsed > intro_timeout:
                    role = detect_role(agent.resume_text) or "hr"

                if role:
                    await agent.update_role(role)
                    await session.say(TRANSITION_PHRASES[InterviewStage.EXPERIENCE])
                    agent.current_stage = InterviewStage.EXPERIENCE
                    agent.stage_start_time = time.time()
                    logging.info(f"Transitioned to {role} mode.")

            # LOGIC: Switch from Experience -> Closing once time is up and the user is quiet
            elif agent.current_stage == InterviewStage.EXPERIENCE:
                silent_for = now - speech_state["last_user_speech"]
                if elapsed > interview_seconds and silent_for >= silence_seconds:
                    await agent.update_instructions(Stage_PROMPTS[InterviewStage.CLOSING])
                    await session.say(TRANSITION_PHRASES[InterviewStage.CLOSING])
                    agent.current_stage = InterviewStage.CLOSING
                    agent.stage_start_time = time.time()
                    logging.info("Transitioned to closing.")
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Stage manager iteration failed; continuing")

    logging.info("--- STAGE MANAGER FINISHED ---")
