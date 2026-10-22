"""Drive OBS through its built-in WebSocket server (OBS 28+)."""
import logging, os, subprocess, time
from pathlib import Path
import obsws_python as obs

logging.getLogger("obsws_python").setLevel(logging.CRITICAL)  # "connection refused" while OBS starts is expected


def client():
    port, password = int(os.environ.get("OBS_PORT", 4455)), os.environ.get("OBS_PASSWORD", "")
    for i in range(30):
        try:
            return obs.ReqClient(host="localhost", port=port, password=password, timeout=5)
        except Exception:
            if i == 0:  # not running yet: launch it and keep trying
                subprocess.Popen(["obs", "--minimize-to-tray", "--disable-shutdown-check"],
                                 start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)
    raise RuntimeError("Could not reach OBS. Is it installed with its WebSocket server enabled? See README.")


def start():
    c = client()
    if c.get_record_status().output_active:
        c.stop_record()
        time.sleep(2)
    c.start_record()


def stop():
    path = Path(client().stop_record().output_path)
    for _ in range(40):  # OBS answers before it has finished writing the file
        size = path.stat().st_size if path.exists() else -1
        time.sleep(0.5)
        if size > 0 and size == path.stat().st_size:
            return path
    raise RuntimeError("OBS did not finish writing the recording.")
