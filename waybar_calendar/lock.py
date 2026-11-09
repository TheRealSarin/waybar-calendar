import fcntl
import logging
import os
import signal
import time

LOG = logging.getLogger(__name__)

PROCESS_MARKER = "waybar_calendar"
ACQUIRE_POLL_SECONDS = 0.05


class InstanceLock:
    def __init__(self, path):
        self.path = path
        self._handle = None

    def acquire(self, timeout=0.0):
        deadline = time.monotonic() + timeout
        while True:
            if self._try_acquire():
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(ACQUIRE_POLL_SECONDS)

    def _try_acquire(self):
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        handle = open(self.path, "a+", encoding="utf-8")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        self._handle = handle
        return True

    def release(self):
        if self._handle is None:
            return
        fcntl.flock(self._handle, fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None

    def running_pid(self):
        try:
            with open(self.path, encoding="utf-8") as handle:
                pid = int(handle.read().strip())
        except (OSError, ValueError):
            return None
        if pid <= 0 or not _is_panel_process(pid):
            return None
        try:
            os.kill(pid, 0)
        except OSError:
            return None
        return pid

    def terminate_running(self):
        pid = self.running_pid()
        if pid is None:
            return False
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as error:
            LOG.warning("could not stop running panel %s: %s", pid, error)
            return False
        return True


def _is_panel_process(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            command = handle.read().decode("utf-8", "replace")
    except OSError:
        return False
    return PROCESS_MARKER in command
