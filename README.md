# Automated-Interview-Platform
A full-stack AI Interviewer platform where candidates upload their resume and undergo a low-latency voice interview. The agent dynamically parses the resume, detects the role (HR, Tech, or Sales), and switches personas to ask relevant, context-aware questions in real-time.

**Tech Stack:**
* **Brain:** Python, LiveKit Agents, Google Gemini (LLM)
* **Speech Processing:** Deepgram (STT & TTS)
* **Body (GUI):** Next.js (React), LiveKit Components
* **Launcher:** Python Tkinter

---

## 🔑 Step 1: Get Your API Keys

You need accounts for these three services. Keep these tabs open!

### 1. LiveKit (Connectivity)
* **URL:** [cloud.livekit.io](https://cloud.livekit.io/)
* Create a project. Go to **Settings** (left sidebar) → **Keys & URLs**.
* You need 3 things:
    1.  **WebSocket URL:** Starts with `wss://...` (e.g., `wss://my-project.livekit.cloud`)
    2.  **API Key:** Starts with `API...`
    3.  **Secret Key:** A long random string.

### 2. Deepgram (Voice)
* **URL:** [console.deepgram.com](https://console.deepgram.com/)
* Create a new API Key.
* Copy the **Key** (it looks like a long hash, e.g., `48a2...`).

### 3. Google Gemini (Intelligence)
* **URL:** [aistudio.google.com](https://aistudio.google.com/)
* Click **"Get API Key"**.
* Copy the key (starts with `AIza...`).

---

## ⚙️ Step 2: Create Configuration Files

You must create **two separate files**. Do not mix them up!

### 📄 File A: Backend Config (Root Folder)
1.  Go to your main folder: `AI-INTERVIEWER/`
2.  Create a new file named exactly: `.env`
3.  Paste the text below and replace the `...` with your actual keys.

```ini
# --- LIVEKIT SETTINGS ---
# Copy "WebSocket URL" from LiveKit Dashboard
LIVEKIT_URL=wss://your-project-name.livekit.cloud

# Copy "API Key"
LIVEKIT_API_KEY=APIabc123...

# Copy "Secret Key"
LIVEKIT_API_SECRET=secXYZ789...



# --- AI SETTINGS ---
# Copy from Deepgram Console
DEEPGRAM_API_KEY=28a...your_deepgram_key...

# Copy from Google AI Studio
GOOGLE_API_KEY=AIza...your_google_key...
```

### 📄 File B: Frontend Config (Frontend Folder)

1. Go to the subfolder: `AI-INTERVIEWER/frontend/`
2. Create a new file named exactly: `.env.local`
3. Paste the text below and replace the `...` with your actual keys.

```ini
# --- LIVEKIT FRONTEND SETTINGS ---
# Copy "WebSocket URL" (Must match File A)
LIVEKIT_URL=wss://your-project-name.livekit.cloud

# Copy the EXACT SAME URL again for Public Access
NEXT_PUBLIC_LIVEKIT_URL=wss://your-project-name.livekit.cloud

# Copy "API Key" (Must match File A)
LIVEKIT_API_KEY=APIabc123...

# Copy "Secret Key" (Must match File A)
LIVEKIT_API_SECRET=secXYZ789...

```

📦 Step 3: Installation
1. Install Backend (Python)
Open a terminal in the root folder (AI-INTERVIEWER/) and install the Python dependencies:
```
pip install -r requirements.txt
```
2. Install Frontend (Next.js)
Open a terminal in the frontend folder (AI-INTERVIEWER/frontend/) and install the Node modules with pnpm (the project's package manager, pinned by `pnpm-lock.yaml`):
```
npx pnpm install
```
🚀 Step 4: How to Run
You need two terminal windows open side-by-side.

Terminal 1: Start the Website (The Room)
```
# Make sure you are in the root 'AI-INTERVIEWER' folder
cd frontend
npm run dev
```
Wait until you see: Ready in ... ms. Leave this running.

Terminal 2: Start the App (The Launcher)
```
# Make sure you are in the root 'AI-INTERVIEWER' folder
python launcher.py
```

## 🐳 Alternative: Run with Docker
No Python or Node install needed, just [Docker](https://www.docker.com/products/docker-desktop/). You still need the two config files from Step 2.
```
cd AI-INTERVIEWER
cp /path/to/your/resume.pdf resume.pdf
docker compose up --build
```
Then open http://localhost:3000 and click "Connect". The Tkinter launcher isn't used with Docker: the agent reads `AI-INTERVIEWER/resume.pdf`. To use a shorter interview, run `INTERVIEW_SECONDS=60 docker compose up`.

## Instructions:
1. The Launcher window will pop up.
2. Click "Browse PDF" $\rightarrow$ Select your Resume.
3. Click "LAUNCH INTERVIEW".
4. Your browser will automatically open localhost:3000.
5. Click "Connect".
6. Start talking! (e.g., "Hi, I'm Alex and I'm applying for the Python Developer role.")

## How the interview flows
1. **Intro:** The agent greets you and asks for your name and the role you're applying for.
2. **Experience:** As soon as it hears a role (technical, sales or HR), it switches to that persona, using your resume as context. If no role is heard within `INTRO_TIMEOUT_SECONDS` (default 45), it guesses the role from your resume, and falls back to HR.
3. **Closing:** After `INTERVIEW_SECONDS` (default 600) in the experience stage, it waits for you to answer the current question and finish speaking, then thanks you and says goodbye. If you don't answer, it closes anyway after a grace period of `INTERVIEW_GRACE_SECONDS` (default 120), so you always have time to think.

These timers can be set in `AI-INTERVIEWER/.env`.


## 🤝 Collaboration & Contributions

Contributions are welcome! Whether you want to **add new interview personas** (e.g., Product Manager, Designer), **improve resume parsing accuracy**, **optimize voice latency**, or **enhance the Next.js UI**, feel free to open an issue or submit a pull request.

Please ensure your work is well-documented and follows the existing modular structure (separating `agents.py`, `prompts.py`, and `frontend/`).
