import os
import sys
import threading
from abc import ABC, abstractmethod
import textwrap
import shutil

from time import sleep
from random import randint

# NB: import doesn't appear to be used but in fact overrides definition for
# the input() method
try:
    import readline
except ImportError:
    import pyreadline as readline


# -------------------------------------------------------------------------
# ABSTRACT

class UserIo(ABC):
    def handle_user_input(self, prompt: str = '') -> str:
        pass

    def handle_basic_output(self, text: str):
        pass

    def handle_story_output(self, text: str):
        self.handle_basic_output(text)

    def start_spinner(self, message: str = '') -> bool:
        return False

    def stop_spinner(self) -> bool:
        return False


class Spinner:
    frames = ("|", "/", "-", "\\")

    def __init__(self, stream=None, interval=0.1):
        self.stream = stream or sys.stdout
        self.interval = interval
        self.message = ''
        self._last_render = ''
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None

    def start(self, message: str = '') -> bool:
        if not self._is_enabled():
            return False

        with self._lock:
            if self._thread and self._thread.is_alive():
                return False

            self.message = message
            self._last_render = ''
            self._stop_event = threading.Event()
            self._thread = threading.Thread(target=self._spin, name="ai-dungeon-spinner", daemon=True)
            self._thread.start()
            return True

    def stop(self) -> bool:
        with self._lock:
            thread = self._thread
            if thread is None:
                return False
            self._stop_event.set()

        thread.join()

        with self._lock:
            self._clear_locked()
            self.message = ''
            self._thread = None
            return True

    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def _is_enabled(self) -> bool:
        isatty = getattr(self.stream, "isatty", None)
        return bool(isatty and isatty())

    def _spin(self):
        frame_index = 0
        while not self._stop_event.is_set():
            frame = self.frames[frame_index % len(self.frames)]
            with self._lock:
                self._render_locked(frame)
            frame_index += 1
            if self._stop_event.wait(self.interval):
                break

    def _render_locked(self, frame: str):
        rendered = frame
        if self.message:
            rendered = "%s %s" % (frame, self.message)

        padding = max(0, len(self._last_render) - len(rendered))
        self.stream.write("\r%s%s" % (rendered, " " * padding))
        self.stream.flush()
        self._last_render = rendered

    def _clear_locked(self):
        if not self._last_render:
            return

        self.stream.write("\r%s\r" % (" " * len(self._last_render)))
        self.stream.flush()
        self._last_render = ''


# -------------------------------------------------------------------------
# IMPLEM: BASIC

class TermIo(UserIo):
    def __init__(self, prompt: str = ''):
        self.prompt = prompt
        self.spinner = Spinner(sys.stdout)

    def handle_user_input(self) -> str:
        self.stop_spinner()
        user_input = input(self.prompt)
        print()
        return user_input

    def handle_basic_output(self, text: str):
        self.stop_spinner()
        for line in text.split("\n"):
            print("\n".join(textwrap.wrap(line, self.get_width())))
        print()

    def start_spinner(self, message: str = '') -> bool:
        return self.spinner.start(message)

    def stop_spinner(self) -> bool:
        return self.spinner.stop()

    # def handle_story_output(self, text: str):
    #     self.handle_basic_output(text)

    def get_width(self):
        terminal_size = shutil.get_terminal_size((80, 20))
        return terminal_size.columns

    def display_splash(self):
        filename = os.path.dirname(os.path.realpath(__file__))
        locale = None
        term = None
        if "LC_ALL" in os.environ:
            locale = os.environ["LC_ALL"]
        if "TERM" in os.environ:
            term = os.environ["TERM"]

        if locale == "C" or (term and term.startswith("vt")):
            filename += "/../res/opening-ascii.txt"
        else:
            filename += "/../res/opening-utf8.txt"

        with open(filename, "r", encoding="utf8") as splash_image:
            print(splash_image.read())

    def clear(self):
        if os.name == "nt":
            _ = os.system("cls")
        else:
            _ = os.system("clear")


# -------------------------------------------------------------------------
# IMPLEM: SLOW TYPING EFFECT

class TermIoSlowStory(TermIo):
    def __init__(self, prompt: str = ''):
        sys.stdout = Unbuffered(sys.stdout)
        super().__init__(prompt)

    def handle_story_output(self, text: str):
        for line in text.split("\n"):
            for line2 in textwrap.wrap(line, self.get_width()):
                for letter in line2:
                    print(letter, end='')
                    sleep(randint(2, 10)*0.005)
                print()
            print()


# allow unbuffered output for slow typing effect
class Unbuffered(object):
   def __init__(self, stream):
       self.stream = stream
   def write(self, data):
       self.stream.write(data)
       self.stream.flush()
   def writelines(self, datas):
       self.stream.writelines(datas)
       self.stream.flush()
   def __getattr__(self, attr):
       return getattr(self.stream, attr)
