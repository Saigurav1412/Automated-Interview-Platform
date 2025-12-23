import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import webbrowser
import os
import sys
import signal

# Global variable to track the background process
agent_process = None

class InterviewLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Interviewer - Setup")
        self.root.geometry("500x300")
        self.resume_path = ""

        # HEADER
        tk.Label(root, text="🤖 AI Interviewer", font=("Helvetica", 24, "bold")).pack(pady=20)
        tk.Label(root, text="Step 1: Upload your Resume", font=("Helvetica", 12)).pack()

        # FILE SELECTION
        self.lbl_status = tk.Label(root, text="No file selected", fg="gray", font=("Helvetica", 10))
        self.lbl_status.pack(pady=5)

        btn_browse = tk.Button(root, text="📂 Browse PDF", command=self.browse_file, height=2, width=20)
        btn_browse.pack(pady=5)

        # START BUTTON
        tk.Label(root, text="Step 2: Start Interview", font=("Helvetica", 12)).pack(pady=(20, 5))
        
        self.btn_start = tk.Button(root, text="🚀 LAUNCH INTERVIEW", command=self.start_interview, 
                                   bg="green", fg="white", font=("Helvetica", 14, "bold"), state=tk.DISABLED)
        self.btn_start.pack(pady=10, fill=tk.X, padx=50)

    def browse_file(self):
        filename = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if filename:
            self.resume_path = filename
            self.lbl_status.config(text=f"✅ Ready: {os.path.basename(filename)}", fg="green")
            self.btn_start.config(state=tk.NORMAL, bg="#00C853") # Enable start button

    def start_interview(self):
        global agent_process
        
        if not self.resume_path:
            messagebox.showwarning("Missing Resume", "Please upload a resume first.")
            return

        # 1. Prepare Environment Variables
        # This passes the file path to 'main.py' safely
        env = os.environ.copy()
        env["GUI_RESUME_PATH"] = self.resume_path

        # 2. Launch the Python Agent in the background
        # It runs: python src/main.py dev
        print(f"--- Launching Agent with Resume: {self.resume_path} ---")
        try:
            # kill previous process if exists
            if agent_process:
                os.kill(agent_process.pid, signal.SIGTERM)
            
            agent_process = subprocess.Popen(
                [sys.executable, "src/main.py", "dev"], 
                env=env,
                cwd=os.getcwd() # Run from root
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start Python Agent:\n{e}")
            return

        # 3. Open the Web Browser automatically
        # Waits 2 seconds for Python to warm up, then opens the room
        root.after(2000, lambda: webbrowser.open("http://localhost:3000"))
        
        # 4. Minimize or Close Launcher
        self.root.iconify() # Minimized

def on_closing():
    """Cleanup when closing the window"""
    if agent_process:
        print("Stopping AI Agent...")
        agent_process.terminate()
    root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = InterviewLauncher(root)
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()