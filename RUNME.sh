#!/bin/sh

# Executed as root by typing ;log runme in the Kindle search bar.
INSTALLER="/mnt/us/native-reading-time-package/Install-Native-Reading-Time-Optimized.sh"
LOG="/mnt/us/reading-time/install.log"

mkdir -p /mnt/us/reading-time
echo "$(date): RUNME entry, uid=$(id -u)" >> "$LOG"

if [ ! -f "$INSTALLER" ]; then
    echo "$(date): ERROR: installer not found: $INSTALLER" >> "$LOG"
    lipc-set-prop com.lab126.system toasterMessage "Installer payload not found" >/dev/null 2>&1 || true
    exit 1
fi

exec /bin/sh "$INSTALLER"
