import json
import platform
import socket
import subprocess
import time


def get_system_facts(target_country: str = "US") -> str:
    try:
        local_tz_offset = -time.timezone / 3600
    except Exception:
        local_tz_offset = 0

    gpu_info = get_hardware_fingerprint()

    facts = {
        "os_system": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "target_proxy_country": target_country,
        "host_tz_offset_hours": local_tz_offset,
        "hardware": gpu_info,
    }
    return json.dumps(facts)


def get_hardware_fingerprint() -> dict:
    gpu_info = _get_gpu_info()
    screen_info = _get_screen_info()

    return {
        "gpu_vendor": gpu_info.get("vendor", "Unknown"),
        "gpu_renderer": gpu_info.get("renderer", "Unknown"),
        "gpu_vram": gpu_info.get("vram", "Unknown"),
        "screen_width": screen_info.get("width", 1920),
        "screen_height": screen_info.get("height", 1080),
        "device_pixel_ratio": screen_info.get("dpr", 2.0),
        "platform_string": _get_platform_string(),
    }


def _get_gpu_info() -> dict:
    system = platform.system()
    gpu = {"vendor": "Apple", "renderer": "Apple M4", "vram": "Shared"}

    try:
        if system == "Darwin":
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            data = json.loads(result.stdout)
            if "SPDisplaysDataType" in data:
                for item in data["SPDisplaysDataType"]:
                    model = item.get("sppci_model") or item.get("_name", "")
                    if model:
                        gpu["renderer"] = model
                        if "M4" in model:
                            gpu["vendor"] = "Apple"
                        elif "M3" in model:
                            gpu["vendor"] = "Apple"
                        elif "M2" in model:
                            gpu["vendor"] = "Apple"
                        elif "M1" in model:
                            gpu["vendor"] = "Apple"
                    cores = item.get("sppci_cores", "")
                    if cores:
                        gpu["vram"] = f"{cores} cores"
                    break

        elif system == "Linux":
            result = subprocess.run(
                ["lspci"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.split("\n"):
                if "VGA" in line or "Display" in line:
                    gpu["renderer"] = line.split(":")[-1].strip()
                    if "NVIDIA" in line:
                        gpu["vendor"] = "NVIDIA"
                    elif "AMD" in line or "Radeon" in line:
                        gpu["vendor"] = "AMD"
                    elif "Intel" in line:
                        gpu["vendor"] = "Intel"
                    break

        elif system == "Windows":
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name,vram"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                gpu["renderer"] = lines[1].strip()
                if "NVIDIA" in gpu["renderer"]:
                    gpu["vendor"] = "NVIDIA"
                elif "AMD" in gpu["renderer"] or "Radeon" in gpu["renderer"]:
                    gpu["vendor"] = "AMD"
                elif "Intel" in gpu["renderer"]:
                    gpu["vendor"] = "Intel"

    except Exception:
        pass

    return gpu


def _get_screen_info() -> dict:
    screen = {"width": 1920, "height": 1080, "dpr": 2.0}

    try:
        system = platform.system()

        if system == "Darwin":
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            data = json.loads(result.stdout)
            if "Display" in data:
                for item in data["Display"]:
                    res = item.get("Resolution", "")
                    if res:
                        parts = res.split("x")
                        if len(parts) == 2:
                            screen["width"] = int(parts[0].strip())
                            screen["height"] = int(parts[1].strip())
                    break

        elif system == "Linux":
            result = subprocess.run(
                ["xrandr", "--listmonitors"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    parts = lines[-1].split()
                    if len(parts) >= 4:
                        res = parts[3].split("x")
                        if len(res) == 2:
                            screen["width"] = int(res[0])
                            screen["height"] = int(res[1])

    except Exception:
        pass

    return screen


def _get_platform_string() -> str:
    system = platform.system()
    if system == "Darwin":
        return "MacIntel"
    elif system == "Windows":
        return "Win32"
    else:
        return "Linux x86_64"
