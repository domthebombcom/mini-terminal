import subprocess, sys, webbrowser, time

print("Starting Mini Terminal...")
proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--port", "8000"])
time.sleep(2)
webbrowser.open("http://localhost:8000")
print("Running at http://localhost:8000 (Ctrl+C to stop)")
try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
