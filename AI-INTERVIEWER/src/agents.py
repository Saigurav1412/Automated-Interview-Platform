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

    def update_role(self, mode):
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
        self.instructions = f"{base_prompt}{context}{rules}"

def detect_role(text):
    text = text.lower()
    if any(x in text for x in ["developer", "engineer", "python", "tech", "code"]):
        return "technical"
    elif any(x in text for x in ["sales", "marketing", "business", "account"]):
        return "sales"
    elif any(x in text for x in ["hr", "recruiter", "manager", "human resources"]):
        return "hr"
    return None

async def run_stage_manager(session: AgentSession, agent: InterviewAgent, speech_state: dict):
    """
    Background task that monitors the conversation.
    """
    logging.info("--- STAGE MANAGER RUNNING ---")
    
    while True:
        await asyncio.sleep(2)
        elapsed = time.time() - agent.stage_start_time
        
        # LOGIC: Switch from Intro -> Experience
        if agent.current_stage == InterviewStage.INTRO:
            # Check if we have enough text to guess the role
            role = detect_role(agent.intro_text)
            
            # Switch if Role found OR time limit reached (45s)
            if role or (elapsed > 45 and len(agent.intro_text) > 50):
                final_mode = role if role else "hr"
                
                # 1. Update State
                agent.current_stage = InterviewStage.EXPERIENCE
                agent.update_role(final_mode)
                
                # 2. Announce Transition (This triggers the AI to speak)
                # We do NOT use llm.complete(). We just tell it to say the transition.
                msg = TRANSITION_PHRASES[InterviewStage.EXPERIENCE]
                await session.generate_reply(instructions=f"Say exactly: '{msg}'")
                
                logging.info(f"Transitioned to {final_mode} mode.")