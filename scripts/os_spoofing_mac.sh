#!/bin/bash
# os_spoofing_mac.sh - Applies TCP/IP level fingerprint spoofing for macOS

echo "[*] macOS Network Fingerprint Tuning Tool"

# 1. Check for root privileges
if [ "$EUID" -ne 0 ]; then
    echo "[!] Please run as root (sudo bash os_spoofing_mac.sh)"
    exit 1
fi

if [ "$1" == "reset" ]; then
    echo "[*] Restoring macOS default TCP parameters..."
    sysctl -w net.inet.tcp.rfc1323=1 > /dev/null
    sysctl -w net.inet.ip.ttl=64 > /dev/null
    # Unload custom pf rules if they exist
    if [ -f /etc/pf.anchors/com.crawler.spoof ]; then
        pfctl -a com.crawler.spoof -F all 2>/dev/null
        rm -f /etc/pf.anchors/com.crawler.spoof
    fi
    echo "[+] Defaults restored."
    exit 0
fi

echo "[*] Applying Windows 10/11 TCP/IP Fingerprint Spoofing to macOS..."

# 2. Modify TTL to 128 (Windows default)
# Note: macOS allows setting default TTL via sysctl directly! No firewall rules needed for this.
echo "  -> Setting default TTL to 128"
sysctl -w net.inet.ip.ttl=128

# 3. Tweak TCP sysctl parameters
echo "  -> Tweaking TCP behaviors"
# Windows rarely uses TCP timestamps by default. macOS controls this via rfc1323.
# 0 = disable RFC 1323 (timestamps and window scaling)
# Note: This is an aggressive change. If you lose connection, run with 'reset' argument.
sysctl -w net.inet.tcp.rfc1323=0

echo ""
echo "[+] macOS Fingerprint successfully spoofed to mimic Windows!"
echo "[!] IMPORTANT: If you experience internet connectivity issues, run:"
echo "    sudo bash src/ai_crawler/utils/os_spoofing_mac.sh reset"
