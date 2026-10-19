"""
litrun Hardware Abstraction Layer
Loads and binds liblitrun_core.so C engine via ctypes, with pure-Python fallback.
"""

from __future__ import annotations
import ctypes
import os
import platform
import re
import sys
from dataclasses import dataclass, asdict
from typing import Optional


class LitrunHwProfileC(ctypes.Structure):
    _fields_ = [
        ("board_name", ctypes.c_char * 128),
        ("soc", ctypes.c_char * 64),
        ("arch", ctypes.c_char * 32),
        ("cpu_part", ctypes.c_char * 32),
        ("cores", ctypes.c_int),
        ("ram_total_mb", ctypes.c_long),
        ("ram_avail_mb", ctypes.c_long),
        ("swap_total_mb", ctypes.c_long),
        ("swap_free_mb", ctypes.c_long),
        ("temp_c", ctypes.c_float),
        ("has_neon", ctypes.c_int),
        ("has_dotprod", ctypes.c_int),
        ("has_i8mm", ctypes.c_int),
        ("has_fp16", ctypes.c_int),
        ("has_sve", ctypes.c_int),
        ("has_avx", ctypes.c_int),
        ("has_avx2", ctypes.c_int),
        ("has_avx512", ctypes.c_int),
        ("has_fma", ctypes.c_int),
        ("has_rknn", ctypes.c_int),
        ("has_nvdla", ctypes.c_int),
        ("profile_id", ctypes.c_char * 64),
    ]


@dataclass
class HardwareProfile:
    board_name: str
    soc: str
    arch: str
    cpu_part: str
    cores: int
    ram_total_mb: int
    ram_avail_mb: int
    swap_total_mb: int
    swap_free_mb: int
    temp_c: float
    has_neon: bool
    has_dotprod: bool
    has_i8mm: bool
    has_fp16: bool
    has_sve: bool
    has_avx: bool
    has_avx2: bool
    has_avx512: bool
    has_fma: bool
    has_rknn: bool
    has_nvdla: bool
    profile_id: str

    def to_dict(self) -> dict:
        return asdict(self)


def _get_core_library_candidates() -> list[str]:
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.environ.get("LITRUN_CORE_LIB", ""),
        os.path.expanduser("~/.cache/litrun/lib/liblitrun_core.so"),
        os.path.join(pkg_dir, "lib", "liblitrun_core.so"),
        os.path.abspath(os.path.join(pkg_dir, "..", "..", "core", "lib", "liblitrun_core.so")),
        "/usr/local/lib/litrun/liblitrun_core.so",
        "/usr/local/lib/liblitrun_core.so",
        "/usr/lib/liblitrun_core.so",
        "liblitrun_core.so",
    ]
    return [p for p in candidates if p and (os.path.isfile(p) or p == "liblitrun_core.so")]


def _find_core_library() -> Optional[str]:
    """Search candidate paths for liblitrun_core.so"""
    for path in _get_core_library_candidates():
        if os.path.isfile(path):
            return path
    return None


_LIB_HANDLE = None


def _get_c_library():
    global _LIB_HANDLE
    if _LIB_HANDLE is not None:
        return _LIB_HANDLE

    for lib_path in _get_core_library_candidates():
        try:
            lib = ctypes.CDLL(lib_path)
            lib.litrun_probe_hardware.argtypes = [ctypes.POINTER(LitrunHwProfileC)]
            lib.litrun_probe_hardware.restype = ctypes.c_int
            lib.litrun_probe_json.restype = ctypes.c_char_p
            lib.litrun_derive_profile_id.argtypes = [
                ctypes.POINTER(LitrunHwProfileC),
                ctypes.c_char_p,
                ctypes.c_size_t,
            ]
            _LIB_HANDLE = lib
            return _LIB_HANDLE
        except (OSError, AttributeError):
            continue

    return None


def _pure_python_probe() -> HardwareProfile:
    """Pure Python fallback probe for environments where C lib is not yet compiled."""
    arch = platform.machine().lower()
    cores = os.cpu_count() or 4
    board_name = "Generic Host"
    soc = arch
    cpu_part = arch

    # Check devicetree model
    for dt_path in ["/sys/firmware/devicetree/base/model", "/proc/device-tree/model"]:
        if os.path.isfile(dt_path):
            try:
                with open(dt_path, "r", errors="ignore") as f:
                    content = f.read().strip("\x00 \t\n\r")
                    if content:
                        board_name = content
                        break
            except Exception:
                pass

    # Check DMI on x86
    if board_name == "Generic Host" and os.path.isfile("/sys/class/dmi/id/product_name"):
        try:
            with open("/sys/class/dmi/id/product_name", "r") as f:
                pname = f.read().strip()
            if pname:
                board_name = pname
        except Exception:
            pass

    # Check /proc/meminfo
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

    # Thermals
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

    # ISA vector flags
    has_neon = arch in ["aarch64", "arm64", "armv7l"]
    has_dotprod = False
    has_i8mm = False
    has_fp16 = False
    has_sve = False
    has_avx = False
    has_avx2 = False
    has_avx512 = False
    has_fma = False

    if os.path.isfile("/proc/cpuinfo"):
        try:
            with open("/proc/cpuinfo", "r") as f:
                content = f.read()
                flags = content.lower()
                has_neon = "neon" in flags or "asimd" in flags
                has_dotprod = "asimddp" in flags or "dotprod" in flags
                has_i8mm = "i8mm" in flags
                has_fp16 = "fphp" in flags or "fp16" in flags
                has_sve = "sve" in flags
                has_avx = "avx" in flags
                has_avx2 = "avx2" in flags
                has_avx512 = "avx512" in flags or "avx512f" in flags
                has_fma = "fma" in flags
        except Exception:
            pass

    # SoC mapping
    if "raspberry pi 5" in board_name.lower():
        soc = "BCM2712"
        cpu_part = "Cortex-A76"
    elif "raspberry pi 4" in board_name.lower():
        soc = "BCM2711"
        cpu_part = "Cortex-A72"
    elif "orange pi 5" in board_name.lower() or "rk3588" in board_name.lower():
        soc = "RK3588"
        cpu_part = "Cortex-A76"

    ram_gb = max(1, round(ram_total_mb / 1024))
    if "raspberry pi 5" in board_name.lower():
        profile_id = f"rpi5-bcm2712-{ram_gb}gb-a76"
    elif "raspberry pi 4" in board_name.lower():
        profile_id = f"rpi4-bcm2711-{ram_gb}gb-a72"
    elif "rk3588" in soc.lower():
        profile_id = f"opi5-rk3588-{ram_gb}gb-a76"
    elif arch == "x86_64":
        profile_id = f"x86-64-avx2-{ram_gb}gb" if has_avx2 else f"x86-64-generic-{ram_gb}gb"
    else:
        profile_id = f"{arch}-{soc}-{ram_gb}gb".lower().replace(" ", "-")

    has_rknn = os.path.exists("/dev/rknpu") or os.path.exists("/dev/rknpu0")
    has_nvdla = os.path.exists("/dev/nvhost-nvdla0") or os.path.exists("/dev/nvhost-ctrl-nvdla")

    return HardwareProfile(
        board_name=board_name,
        soc=soc,
        arch=arch,
        cpu_part=cpu_part,
        cores=cores,
        ram_total_mb=ram_total_mb,
        ram_avail_mb=ram_avail_mb,
        swap_total_mb=swap_total_mb,
        swap_free_mb=swap_free_mb,
        temp_c=temp_c,
        has_neon=has_neon,
        has_dotprod=has_dotprod,
        has_i8mm=has_i8mm,
        has_fp16=has_fp16,
        has_sve=has_sve,
        has_avx=has_avx,
        has_avx2=has_avx2,
        has_avx512=has_avx512,
        has_fma=has_fma,
        has_rknn=has_rknn,
        has_nvdla=has_nvdla,
        profile_id=profile_id,
    )


def probe_hardware() -> HardwareProfile:
    """Probes the host embedded Linux hardware using C core if available, or Python fallback."""
    lib = _get_c_library()
    if lib is not None:
        c_prof = LitrunHwProfileC()
        rc = lib.litrun_probe_hardware(ctypes.byref(c_prof))
        if rc == 0:
            return HardwareProfile(
                board_name=c_prof.board_name.decode("utf-8", "ignore"),
                soc=c_prof.soc.decode("utf-8", "ignore"),
                arch=c_prof.arch.decode("utf-8", "ignore"),
                cpu_part=c_prof.cpu_part.decode("utf-8", "ignore"),
                cores=c_prof.cores,
                ram_total_mb=c_prof.ram_total_mb,
                ram_avail_mb=c_prof.ram_avail_mb,
                swap_total_mb=c_prof.swap_total_mb,
                swap_free_mb=c_prof.swap_free_mb,
                temp_c=round(c_prof.temp_c, 1),
                has_neon=bool(c_prof.has_neon),
                has_dotprod=bool(c_prof.has_dotprod),
                has_i8mm=bool(c_prof.has_i8mm),
                has_fp16=bool(c_prof.has_fp16),
                has_sve=bool(c_prof.has_sve),
                has_avx=bool(c_prof.has_avx),
                has_avx2=bool(c_prof.has_avx2),
                has_avx512=bool(c_prof.has_avx512),
                has_fma=bool(c_prof.has_fma),
                has_rknn=bool(c_prof.has_rknn),
                has_nvdla=bool(c_prof.has_nvdla),
                profile_id=c_prof.profile_id.decode("utf-8", "ignore"),
            )

    return _pure_python_probe()

