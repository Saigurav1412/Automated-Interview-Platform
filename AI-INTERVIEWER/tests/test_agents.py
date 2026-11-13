import asyncio
import time

import pytest

from agents import InterviewAgent, detect_role, run_stage_manager
from prompts import PERSONA_OVERRIDES, Stage_PROMPTS, TRANSITION_PHRASES
from stages import InterviewStage


# ---------- detect_role ----------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("I'm applying for the Python developer role", "technical"),
        ("I am a software engineer", "technical"),
        ("I work in engineering", "technical"),
        ("I love coding", "technical"),
        ("I'm interviewing for a sales position", "sales"),
        ("Marketing lead", "sales"),
        ("I'd like the HR role", "hr"),
        ("Human Resources generalist", "hr"),
        ("I'm a recruiter", "hr"),
    ],
)
def test_detect_role_matches(text, expected):
    assert detect_role(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "I have three years of experience",  # "hr" inside "three"
        "I like to decode puzzles",          # "code" inside "decode"
        "My name is Alex Thrasher",          # "hr" inside "Thrasher"
        "I enjoy architecture",              # "tech" inside "architecture"
        "Hello there",
        "",
        None,
    ],
)
def test_detect_role_no_false_positives(text):
    assert detect_role(text) is None


# ---------- stage manager ----------

class FakeSession:
    def __init__(self, fail_times=0):
        self.said = []
        self.fail_times = fail_times

    async def say(self, text):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("transient TTS failure")
        self.said.append(text)


FAST = dict(poll_interval=0.01, silence_seconds=0.1)


async def wait_for(cond, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not cond():
        if time.monotonic() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.01)


def start(session, agent, speech_state, **kwargs):
    opts = {**FAST, "intro_timeout": 60, "interview_seconds": 60, **kwargs}
    return asyncio.create_task(run_stage_manager(session, agent, speech_state, **opts))


async def stop(task):
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def test_role_in_intro_switches_persona_with_resume():
    session = FakeSession()
    agent = InterviewAgent(resume_text="Jane Doe - 5 years in retail")
    task = start(session, agent, {"last_user_speech": time.time()})
    try:
        agent.intro_text = " Hi, I'm Jane, applying for a sales role"
        await wait_for(lambda: agent.current_stage == InterviewStage.EXPERIENCE)
        assert PERSONA_OVERRIDES["sales"] in agent.instructions
        assert "Jane Doe - 5 years in retail" in agent.instructions
        assert session.said == [TRANSITION_PHRASES[InterviewStage.EXPERIENCE]]
    finally:
        await stop(task)


async def test_no_switch_before_intro_timeout():
    session = FakeSession()
    agent = InterviewAgent(resume_text="Python developer")
    task = start(session, agent, {"last_user_speech": time.time()})
    try:
        await asyncio.sleep(0.1)
        assert agent.current_stage == InterviewStage.INTRO
        assert session.said == []
    finally:
        await stop(task)


async def test_intro_timeout_falls_back_to_resume():
    session = FakeSession()
    agent = InterviewAgent(resume_text="Senior Python developer, 6 years")
    agent.intro_text = " hello there"  # no role mentioned
    task = start(session, agent, {"last_user_speech": time.time()}, intro_timeout=0.05)
    try:
        await wait_for(lambda: agent.current_stage == InterviewStage.EXPERIENCE)
        assert PERSONA_OVERRIDES["technical"] in agent.instructions
    finally:
        await stop(task)


async def test_intro_timeout_falls_back_to_hr_without_resume_role():
    session = FakeSession()
    agent = InterviewAgent(resume_text="")  # no resume, and intro is empty
    task = start(session, agent, {"last_user_speech": time.time()}, intro_timeout=0.05)
    try:
        await wait_for(lambda: agent.current_stage == InterviewStage.EXPERIENCE)
        assert PERSONA_OVERRIDES["hr"] in agent.instructions
    finally:
        await stop(task)


async def test_closing_waits_for_silence():
    session = FakeSession()
    agent = InterviewAgent()
    agent.current_stage = InterviewStage.EXPERIENCE
    agent.stage_start_time = time.time() - 100  # budget already exceeded
    speech_state = {"last_user_speech": time.time()}
    task = start(session, agent, speech_state, interview_seconds=1, silence_seconds=0.3)
    try:
        # Keep "talking" for a while: must not close
        for _ in range(10):
            speech_state["last_user_speech"] = time.time()
            await asyncio.sleep(0.03)
        assert agent.current_stage == InterviewStage.EXPERIENCE
        assert session.said == []

        # Go quiet: closes
        await wait_for(lambda: agent.current_stage == InterviewStage.CLOSING)
        assert agent.instructions == Stage_PROMPTS[InterviewStage.CLOSING]
        assert session.said == [TRANSITION_PHRASES[InterviewStage.CLOSING]]
        await asyncio.wait_for(task, 1)  # manager finishes after closing
    finally:
        await stop(task)


async def test_full_flow_resets_stage_timer():
    session = FakeSession()
    agent = InterviewAgent()
    agent.intro_text = " I'm a recruiter"
    task = start(session, agent, {"last_user_speech": 0}, interview_seconds=0.2)
    try:
        await wait_for(lambda: agent.current_stage == InterviewStage.EXPERIENCE)
        switched_at = time.time()
        await wait_for(lambda: agent.current_stage == InterviewStage.CLOSING)
        # Closing must wait for the experience budget measured from the transition
        assert time.time() - switched_at >= 0.15
        assert session.said == [
            TRANSITION_PHRASES[InterviewStage.EXPERIENCE],
            TRANSITION_PHRASES[InterviewStage.CLOSING],
        ]
    finally:
        await stop(task)


async def test_manager_survives_transient_exception(caplog):
    session = FakeSession(fail_times=1)
    agent = InterviewAgent()
    agent.intro_text = " applying as an engineer"
    task = start(session, agent, {"last_user_speech": time.time()})
    try:
        await wait_for(lambda: agent.current_stage == InterviewStage.EXPERIENCE)
        assert not task.done()
        assert session.said == [TRANSITION_PHRASES[InterviewStage.EXPERIENCE]]
        assert "Stage manager iteration failed" in caplog.text
    finally:
        await stop(task)
