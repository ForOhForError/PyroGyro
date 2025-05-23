#
# BSD 2-Clause License
#
# Copyright (c) 2018, Dane Finlay
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

# See https://github.com/drmfinlay/windows-fun/

import ctypes
import ctypes.wintypes
import threading

import psutil

EVENT_SYSTEM_DIALOGSTART = 0x0010
EVENT_SYSTEM_CAPTURESTART = 0x0008
EVENT_SYSTEM_MENUPOPUPSTART = 0x0006
WINEVENT_OUTOFCONTEXT = 0x0000
EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_SKIPOWNPROCESS = 0x0002

HANDLE_SYSTEM_EVENTS = (
    EVENT_SYSTEM_FOREGROUND,
    EVENT_SYSTEM_DIALOGSTART,
    EVENT_SYSTEM_CAPTURESTART,
    EVENT_SYSTEM_MENUPOPUPSTART,
)

user32 = ctypes.windll.user32
ole32 = ctypes.windll.ole32
EnumWindows = ctypes.windll.user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(
    ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
)
WinEventProcType = ctypes.WINFUNCTYPE(
    None,
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.HWND,
    ctypes.wintypes.LONG,
    ctypes.wintypes.LONG,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD,
)
GetWindowText = ctypes.windll.user32.GetWindowTextW
GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId
IsWindowVisible = ctypes.windll.user32.IsWindowVisible
SetTimer = ctypes.windll.user32.SetTimer
KillTimer = ctypes.windll.user32.KillTimer
GetForegroundWindow = ctypes.windll.user32.GetForegroundWindow

import logging


def _hwnd_to_names(hwnd):
    length = GetWindowTextLength(hwnd)
    namebuff = ctypes.create_unicode_buffer(length + 1)
    GetWindowText(hwnd, namebuff, length + 1)
    pid = ctypes.wintypes.LPDWORD(ctypes.c_ulong(0))
    GetWindowThreadProcessId(hwnd, pid)
    proc = psutil.Process(pid.contents.value)
    return proc.name(), namebuff.value


class WindowChangeEventListener(object):
    """
    WindowChangeEventListener
    """

    def __init__(self, callback=None):
        self.running = False
        self.hooks = set()
        self.focus_exe_name = ""
        self.focus_window_title = ""
        if callback:
            self.callback = callback
        else:
            self.callback = self.default_callback

    def default_callback(self, proc_name, window_name):
        logging.debug(f"{proc_name}, {window_name}")

    def process_current_window(self):
        hwnd = GetForegroundWindow()
        self.focus_exe_name, self.focus_window_title = _hwnd_to_names(hwnd)
        self.callback(self.focus_exe_name, self.focus_window_title)

    def listen(self, handle_event=None):
        ole32.CoInitialize(0)

        def win_callback(
            hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime
        ):
            exe_name, window_title = _hwnd_to_names(hwnd)
            if (
                self.focus_exe_name == exe_name
                and self.focus_window_title == window_title
            ):
                pass
            else:
                self.focus_exe_name, self.focus_window_title = _hwnd_to_names(hwnd)
                self.callback(self.focus_exe_name, self.focus_window_title)

        WinEventProc = WinEventProcType(win_callback)
        for event_id in HANDLE_SYSTEM_EVENTS:
            hook = user32.SetWinEventHook(
                event_id,
                event_id,
                0,
                WinEventProc,
                0,
                0,
                WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
            )
            if hook == 0:
                logging.error("SetWinEventHook failed")
            else:
                self.hooks.add(hook)
        self.running = True
        timer = SetTimer(0, 0, 100, 0)
        msg = ctypes.wintypes.MSG()
        while self.running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0):
            user32.TranslateMessage(msg)
            user32.DispatchMessageW(msg)
        KillTimer(0, timer)
        for hook in self.hooks:
            user32.UnhookWinEvent(hook)
        ole32.CoUninitialize()

    def listen_in_thread(self):
        listen_thread = threading.Thread(target=self.listen, daemon=True)
        listen_thread.start()
        return listen_thread

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.stop()

    def stop(self):
        self.running = False

    def get_current_focus(self):
        return self.focus_exe_name, self.focus_window_title
