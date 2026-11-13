import os
import re
import time
import asyncio
import logging
from livekit.agents import StopResponse
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
            "\n- You have just asked the candidate to introduce themselves. Let them finish,"
            " acknowledge it briefly, and only then move on to their resume and role topics."
            "\n- If the candidate asks to skip a question, say that's fine and ask a different one."
            "\n- Ask exactly ONE question at a time. Never combine two questions in one turn."
            "\n- Wait for the user to answer."
            "\n- Keep responses short: at most a brief acknowledgement plus one question, under 25 words."
            "\n- This is a spoken conversation: use plain, natural words. No lists, markdown, or symbols."
            "\n- Use the resume only to choose topics. Ask about one specific item at a time; never read it back."
            "\n- If an answer sounds cut off, invite the candidate to continue instead of changing topic."
        )

        # 4. What the candidate already told us (their name/role turn is not
        # replied to by the LLM, so keep it in the instructions)
        intro = ""
        if self.intro_text.strip():
            intro = f"\n\nCANDIDATE'S OPENING (name and role): {self.intro_text.strip()}"

        # 5. Update the Agent's instructions dynamically
        await self.update_instructions(f"{base_prompt}{context}{intro}{rules}")

    async def start_experience(self, session, role):
        """Switch to the role's persona and ask the candidate to introduce themselves."""
        if self.current_stage != InterviewStage.INTRO:
            return
        # Claim the transition first so the hook and the stage manager can't both run it
        self.current_stage = InterviewStage.EXPERIENCE
        try:
            await self.update_role(role)
            # Drop any reply still generated under the intro prompt
            await session.interrupt()
            await session.say(TRANSITION_PHRASES[InterviewStage.EXPERIENCE])
        except Exception:
            self.current_stage = InterviewStage.INTRO  # let the stage manager retry
            raise
        self.stage_start_time = time.time()
        logging.info(f"Transitioned to {role} mode.")

    async def on_user_turn_completed(self, turn_ctx, new_message):
        """Runs after the candidate finishes a turn, before the LLM replies.

        When the intro turn names a role, switch stages here so the LLM never gets a
        chance to jump straight into interview questions under the intro prompt.
        """
        if self.current_stage != InterviewStage.INTRO:
            return
        text = new_message.text_content or ""
        if text and text not in self.intro_text:
            self.intro_text += " " + text
        role = detect_role(self.intro_text)
        if role:
            await self.start_experience(self.session, role)
            raise StopResponse()  # the transition phrase is this turn's reply

# Word-boundary patterns so e.g. "hr" doesn't match "three" and "code" doesn't match "decode"
ROLE_PATTERNS = [
    ("technical", re.compile(r"\b(developers?|engineer(s|ing)?|python|tech(nical)?|cod(e|er|ers|ing)|software|sde|sd|swe|s d e)\b")),
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
    grace_seconds: float | None = None,
):
    """
    Background task that monitors the conversation.
    """
    if intro_timeout is None:
        intro_timeout = float(os.getenv("INTRO_TIMEOUT_SECONDS", "45"))
    if interview_seconds is None:
        interview_seconds = float(os.getenv("INTERVIEW_SECONDS", "600"))
    if grace_seconds is None:
        grace_seconds = float(os.getenv("INTERVIEW_GRACE_SECONDS", "120"))

    logging.info("--- STAGE MANAGER RUNNING ---")

    while agent.current_stage != InterviewStage.CLOSING:
        await asyncio.sleep(poll_interval)
        try:
            now = time.time()
            elapsed = now - agent.stage_start_time

            # LOGIC: Intro -> Experience fallback. A role named in conversation is
            # handled immediately by InterviewAgent.on_user_turn_completed; this only
            # covers a candidate who never names one: use the resume, then HR.
            if agent.current_stage == InterviewStage.INTRO:
                if elapsed > intro_timeout:
                    role = (
                        detect_role(agent.intro_text)
                        or detect_role(agent.resume_text)
                        or "hr"
                    )
                    await agent.start_experience(session, role)

            # LOGIC: Switch from Experience -> Closing once time is up and the user is quiet.
            # Never close while the agent is thinking or speaking (e.g. replying to
            # "can we skip this one?"), and don't cut off a candidate who is still
            # thinking: wait until they have answered the agent's latest question
            # (spoken after both the time ran out and the agent last finished
            # speaking), or until the grace period has also run out.
            elif agent.current_stage == InterviewStage.EXPERIENCE:
                last_speech = speech_state["last_user_speech"]
                last_agent_end = speech_state.get("last_agent_speech_end", 0)
                agent_busy = speech_state.get("agent_busy", False)
                silent_for = now - last_speech
                time_up_at = agent.stage_start_time + interview_seconds
                answered_latest_question = last_speech > max(time_up_at, last_agent_end)
                grace_over = elapsed > interview_seconds + grace_seconds
                if (
                    elapsed > interview_seconds
                    and not agent_busy
                    and silent_for >= silence_seconds
                    and (answered_latest_question or grace_over)
                ):
                    await agent.update_instructions(Stage_PROMPTS[InterviewStage.CLOSING])
                    await session.interrupt()
                    await session.say(TRANSITION_PHRASES[InterviewStage.CLOSING])
                    agent.current_stage = InterviewStage.CLOSING
                    agent.stage_start_time = time.time()
                    logging.info("Transitioned to closing.")
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Stage manager iteration failed; continuing")

    logging.info("--- STAGE MANAGER FINISHED ---")
