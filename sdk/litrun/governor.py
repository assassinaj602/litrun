"""
litrun Active Resource Governor
Enforces hard RAM ceilings, monitors swap and thermal zones, blocks dangerous allocations.
"""

from __future__ import annotations
import ctypes
import os
from dataclasses import dataclass, asdict
from typing import Tuple, Optional
from litrun.hardware import _get_c_library


class LitrunGovernorStatusC(ctypes.Structure):
    _fields_ = [
        ("cgroup_version", ctypes.c_int),
        ("cgroup_mem_usage_mb", ctypes.c_long),
        ("cgroup_mem_limit_mb", ctypes.c_long),
        ("ram_total_mb", ctypes.c_long),
        ("ram_avail_mb", ctypes.c_long),
        ("swap_total_mb", ctypes.c_long),
        ("swap_free_mb", ctypes.c_long),
        ("temp_c", ctypes.c_float),
        ("thermal_state", ctypes.c_int),
        ("online_cores", ctypes.c_int),
        ("recommended_threads", ctypes.c_int),
    ]


@dataclass
class GovernorStatus:
    cgroup_version: int
    cgroup_mem_usage_mb: int
    cgroup_mem_limit_mb: int
    ram_total_mb: int
    ram_avail_mb: int
    swap_total_mb: int
    swap_free_mb: int
    temp_c: float
    thermal_state: str  # "nominal", "warm", "critical"
    online_cores: int
    recommended_threads: int

    def to_dict(self) -> dict:
        return asdict(self)


THERMAL_STATE_MAP = {
    0: "nominal",
    1: "warm",
    2: "critical",
}


def poll_governor() -> GovernorStatus:
    """Polls current memory, cgroup limits, thermals, and recommended thread concurrency."""
    lib = _get_c_library()
    if lib is not None:
        try:
            lib.litrun_governor_poll.argtypes = [ctypes.POINTER(LitrunGovernorStatusC)]
            lib.litrun_governor_poll.restype = ctypes.c_int
            c_gov = LitrunGovernorStatusC()
            if lib.litrun_governor_poll(ctypes.byref(c_gov)) == 0:
                return GovernorStatus(
                    cgroup_version=c_gov.cgroup_version,
                    cgroup_mem_usage_mb=c_gov.cgroup_mem_usage_mb,
                    cgroup_mem_limit_mb=c_gov.cgroup_mem_limit_mb,
                    ram_total_mb=c_gov.ram_total_mb,
                    ram_avail_mb=c_gov.ram_avail_mb,
                    swap_total_mb=c_gov.swap_total_mb,
                    swap_free_mb=c_gov.swap_free_mb,
                    temp_c=round(c_gov.temp_c, 1),
                    thermal_state=THERMAL_STATE_MAP.get(c_gov.thermal_state, "nominal"),
                    online_cores=c_gov.online_cores,
                    recommended_threads=c_gov.recommended_threads,
                )
        except Exception:
            pass

    # Pure Python fallback
    ram_total_mb = 1024
    ram_avail_mb = 512
    swap_total_mb = 0
    swap_free_mb = 0

    if os.path.isfile("/proc/meminfo"):
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        ram_total_mb = int(line.split()[1]) // 1024
                    elif line.startswith("MemAvailable:"):
                        ram_avail_mb = int(line.split()[1]) // 1024
                    elif line.startswith("SwapTotal:"):
                        swap_total_mb = int(line.split()[1]) // 1024
                    elif line.startswith("SwapFree:"):
                        swap_free_mb = int(line.split()[1]) // 1024
        except Exception:
            pass

    temp_c = -1.0
    for zone in range(5):
        tpath = f"/sys/class/thermal/thermal_zone{zone}/temp"
        if os.path.isfile(tpath):
            try:
                with open(tpath, "r") as f:
                    milli = int(f.read().strip())
                    if milli > 0:
                        temp_c = milli / 1000.0
                        break
            except Exception:
                pass

    if temp_c >= 80.0:
        thermal_state = "critical"
    elif temp_c >= 75.0:
        thermal_state = "warm"
    else:
        thermal_state = "nominal"

    online_cores = os.cpu_count() or 4
    if thermal_state == "critical":
        recommended_threads = max(1, online_cores // 2)
    elif thermal_state == "warm":
        recommended_threads = max(1, online_cores - 1)
    else:
        recommended_threads = max(1, online_cores - 1) if online_cores >= 4 else online_cores

    return GovernorStatus(
        cgroup_version=0,
        cgroup_mem_usage_mb=-1,
        cgroup_mem_limit_mb=-1,
        ram_total_mb=ram_total_mb,
        ram_avail_mb=ram_avail_mb,
        swap_total_mb=swap_total_mb,
        swap_free_mb=swap_free_mb,
        temp_c=temp_c,
        thermal_state=thermal_state,
        online_cores=online_cores,
        recommended_threads=recommended_threads,
    )


def check_ram_envelope(
    model_size_mb: int,
    context_length: int = 2048,
    kv_bytes_per_token: float = 32.0,
    overhead_mb: int = 250,
    safety_ratio: float = 0.85,
) -> Tuple[bool, int, str, bool]:
    """
    Evaluates whether the proposed model fits within the device's safe RAM envelope.

    RAM_needed = Model Size + (Context Length * KV Cache per Token) + 250MB (Runtime Overhead)

    Returns:
        (allowed: bool, ram_needed_mb: int, reason: str, requires_downgrade: bool)
    """
    gov = poll_governor()

    kv_cache_mb = int((context_length * kv_bytes_per_token) / (1024 * 1024))
    ram_needed = model_size_mb + kv_cache_mb + overhead_mb

    effective_avail = gov.ram_avail_mb
    if gov.cgroup_mem_limit_mb > 0 and gov.cgroup_mem_usage_mb >= 0:
        cgroup_headroom = gov.cgroup_mem_limit_mb - gov.cgroup_mem_usage_mb
        if cgroup_headroom < effective_avail:
            effective_avail = max(0, cgroup_headroom)

    safe_ceiling = int(effective_avail * safety_ratio)

    if ram_needed > effective_avail:
        reason = (
            f"OOM RISK: Required {ram_needed}MB exceeds available system RAM "
            f"({effective_avail}MB free). Execution blocked to protect kernel stability."
        )
        return (False, ram_needed, reason, True)

    if ram_needed > safe_ceiling:
        reason = (
            f"TIGHT MEMORY: Required {ram_needed}MB exceeds 85% safety ceiling "
            f"({safe_ceiling}MB / {effective_avail}MB free). Downgrading to a more compact quantization is recommended."
        )
        return (True, ram_needed, reason, True)

    pct = int((ram_needed / effective_avail) * 100) if effective_avail > 0 else 0
    reason = f"PASS: {ram_needed}MB required out of {effective_avail}MB available ({pct}% envelope)."
    return (True, ram_needed, reason, False)
