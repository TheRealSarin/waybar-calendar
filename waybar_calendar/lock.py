import fcntl
import logging
import os
import signal

LOG = logging.getLogger(__name__)


class InstanceLock:
    def __init__(self, path):
        self.path = path
        self._handle = None

    def acquire(self):
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
        if pid <= 0:
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
