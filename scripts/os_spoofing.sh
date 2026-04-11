#!/bin/bash
# os_spoofing.sh - Applies TCP/IP level fingerprint spoofing (Run as root on Linux)

echo "[*] Applying Windows 10/11 TCP/IP Fingerprint Spoofing..."

# 1. Check if running on Linux
if [ "$(uname)" != "Linux" ]; then
    echo "[!] This script only works on Linux. Current OS: $(uname)"
    echo "    On macOS/Windows, please use a VM or Docker to test TCP stack spoofing."
    exit 1
fi

# 2. Check for root privileges
if [ "$EUID" -ne 0 ]; then
    echo "[!] Please run as root (sudo)"
    exit 1
fi

# 3. Spoof TTL to 128 (Windows default)
echo "[*] Setting outbound TTL to 128..."
iptables -t mangle -C POSTROUTING -j TTL --ttl-set 128 2>/dev/null || iptables -t mangle -A POSTROUTING -j TTL --ttl-set 128

# 4. Modify TCP options via sysctl to mimic Windows behavior
echo "[*] Tweaking TCP sysctl parameters..."
# Windows rarely uses TCP timestamps by default
sysctl -w net.ipv4.tcp_timestamps=0
# Adjust SYN retries
sysctl -w net.ipv4.tcp_syn_retries=2
# Adjust FIN timeout
sysctl -w net.ipv4.tcp_fin_timeout=30

echo "[+] OS Fingerprint successfully spoofed to mimic Windows!"
echo "    Note: To persist these changes after reboot, you need to save iptables rules and edit /etc/sysctl.conf"
