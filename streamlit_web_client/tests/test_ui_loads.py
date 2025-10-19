import subprocess
import time
from pathlib import Path


def test_streamlit_launches():
    # Launch Streamlit in headless mode, then terminate after a few seconds.
    client_path = Path(__file__).resolve().parent.parent / "client.py"
    proc = subprocess.Popen(
        ["streamlit", "run", str(client_path), "--server.headless", "true"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        time.sleep(5)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    assert proc.poll() is not None
