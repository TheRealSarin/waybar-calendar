import os
import subprocess
import sys
import tempfile
import time
import unittest

from waybar_calendar.lock import InstanceLock

HOLDER = """
import sys
import time
sys.path.insert(0, sys.argv[2])
from waybar_calendar.lock import InstanceLock

lock = InstanceLock(sys.argv[1])
if not lock.acquire():
    sys.exit(2)
print("locked", flush=True)
time.sleep(30)
"""


class InstanceLockTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.directory.name, "panel.lock")
        self.repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def tearDown(self):
        self.directory.cleanup()

    def test_acquire_writes_pid(self):
        lock = InstanceLock(self.path)
        self.assertTrue(lock.acquire())
        try:
            with open(self.path, encoding="utf-8") as handle:
                self.assertEqual(handle.read().strip(), str(os.getpid()))
        finally:
            lock.release()

    def test_second_process_cannot_acquire_and_can_be_stopped(self):
        holder = subprocess.Popen(
            [sys.executable, "-c", HOLDER, self.path, self.repo],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(holder.stdout.readline().strip(), "locked")
            lock = InstanceLock(self.path)
            self.assertFalse(lock.acquire())
            self.assertEqual(lock.running_pid(), holder.pid)
            self.assertTrue(lock.terminate_running())
            self.assertEqual(holder.wait(timeout=10), -15)
        finally:
            if holder.poll() is None:
                holder.kill()
                holder.wait(timeout=5)

    def test_released_lock_can_be_taken_again(self):
        first = InstanceLock(self.path)
        self.assertTrue(first.acquire())
        first.release()
        second = InstanceLock(self.path)
        self.assertTrue(second.acquire())
        second.release()

    def test_missing_pid_file_reports_nothing_running(self):
        lock = InstanceLock(os.path.join(self.directory.name, "absent.lock"))
        self.assertIsNone(lock.running_pid())
        self.assertFalse(lock.terminate_running())

    def test_garbage_pid_file_reports_nothing_running(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("not a pid")
        self.assertIsNone(InstanceLock(self.path).running_pid())

    def test_pid_belonging_to_another_program_is_not_ours_to_kill(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("1")
        lock = InstanceLock(self.path)
        self.assertIsNone(lock.running_pid())
        self.assertFalse(lock.terminate_running())

    def test_acquire_with_a_timeout_still_refuses_a_held_lock(self):
        holder = subprocess.Popen(
            [sys.executable, "-c", HOLDER, self.path, self.repo],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(holder.stdout.readline().strip(), "locked")
            started = time.monotonic()
            self.assertFalse(InstanceLock(self.path).acquire(timeout=0.2))
            self.assertGreaterEqual(time.monotonic() - started, 0.2)
        finally:
            holder.kill()
            holder.wait(timeout=5)
