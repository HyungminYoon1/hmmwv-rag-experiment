"""Explicit, process-local CPU placement for this experiment on Windows."""
from __future__ import annotations

import ctypes
import os
import struct


def windows_cpu_sets():
    if os.name != 'nt':
        raise ValueError('The recorded CPU placement requires Windows')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    size = ctypes.c_ulong()
    kernel.GetSystemCpuSetInformation(None, 0, ctypes.byref(size), None, 0)
    buffer = ctypes.create_string_buffer(size.value)
    if not kernel.GetSystemCpuSetInformation(buffer, size.value, ctypes.byref(size), None, 0):
        raise OSError(ctypes.get_last_error(), 'Cannot read CPU topology')
    offset = 0
    rows = []
    while offset < size.value:
        length, kind = struct.unpack_from('<II', buffer.raw, offset)
        if length < 8 or offset + length > size.value:
            raise ValueError('Invalid CPU topology record')
        if kind == 0:
            cpu_id, group, logical, core, cache, numa, efficiency, flags = struct.unpack_from('<IHBBBBBB', buffer.raw, offset + 8)
            rows.append({'logical': logical, 'core': core, 'group': group, 'efficiency': efficiency})
        offset += length
    return rows


def process_affinity():
    if os.name != 'nt':
        return sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
    process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
    if not kernel.GetProcessAffinityMask(kernel.GetCurrentProcess(), ctypes.byref(process_mask), ctypes.byref(system_mask)):
        raise OSError(ctypes.get_last_error(), 'Cannot read process CPU placement')
    return [i for i in range(ctypes.sizeof(ctypes.c_size_t) * 8) if process_mask.value & (1 << i)]


def apply_cpu_policy(config):
    selected = config['cpu_logical_processors']
    topology = [row for row in windows_cpu_sets() if row['group'] == 0]
    rows = {row['logical']: row for row in topology}
    if (not selected or len(set(selected)) != len(selected) or not set(selected) <= set(rows)
        or len({rows[i]['core'] for i in selected}) != len(selected)
        or any(rows[i]['efficiency'] != max(r['efficiency'] for r in topology) for i in selected)):
        raise ValueError('Configured CPUs do not match distinct performance cores on this PC')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(), sum(1 << i for i in selected)):
        raise OSError(ctypes.get_last_error(), 'Cannot apply process-local CPU placement')
    if process_affinity() != sorted(selected):
        raise ValueError('Process CPU placement was not applied')
