"""Read-only native process probes, independent of Career state and settings."""
from __future__ import annotations

import os
from pathlib import Path


def _windows_process_running(pid, kernel=None):
    import ctypes
    from ctypes import wintypes
    kernel = kernel or ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only.
    if not handle:
        return False if ctypes.get_last_error() in (87, 1168) else None
    try:
        waited = kernel.WaitForSingleObject(handle, 0)
        return True if waited == 258 else False if waited == 0 else None
    finally:
        kernel.CloseHandle(handle)


def process_running(pid):
    """True/False/None; a terminated Windows process object is not running."""
    if type(pid) is not int or pid <= 0:
        return None
    if os.name == 'nt':
        return _windows_process_running(pid)
    try:
        text = (Path('/proc') / str(pid) / 'stat').read_text('utf-8')
        return text.rsplit(')', 1)[1].split()[0] not in ('Z', 'X')
    except FileNotFoundError:
        return False if Path('/proc').is_dir() else None
    except (OSError, IndexError):
        return None


def _windows_cs2_running():
    import ctypes
    from ctypes import wintypes
    class ProcessEntry(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                   ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
                   ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                   ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG),
                   ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
    kernel.Process32FirstW.restype = wintypes.BOOL
    kernel.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
    kernel.Process32NextW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle in (None, ctypes.c_void_p(-1).value):
        return None
    uncertain = False
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        found = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while found:
            if entry.szExeFile.casefold() == 'cs2.exe':
                live = _windows_process_running(entry.th32ProcessID, kernel)
                if live is True:
                    return True
                uncertain = uncertain or live is None
            found = kernel.Process32NextW(handle, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES: normal EOF.
            return None
        return None if uncertain else False
    finally:
        kernel.CloseHandle(handle)


def cs2_running():
    """Lightweight tri-state query; no PowerShell or external command is run."""
    if os.name == 'nt':
        return _windows_cs2_running()
    root = Path('/proc')
    if not root.is_dir():
        return None
    uncertain = False
    try:
        for child in root.iterdir():
            if not child.name.isdigit():
                continue
            try:
                name = (child / 'comm').read_text('utf-8').strip().casefold()
            except FileNotFoundError:
                continue  # Exited since the directory inventory.
            except OSError:
                uncertain = True
                continue
            if name not in ('cs2', 'cs2.exe'):
                continue
            live = process_running(int(child.name))
            if live is True:
                return True
            uncertain = uncertain or live is None
    except OSError:
        return None
    return None if uncertain else False
