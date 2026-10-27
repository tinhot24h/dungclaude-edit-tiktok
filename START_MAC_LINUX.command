#!/bin/sh
cd "$(dirname "$0")" || exit 1
python3 launch.py
result=$?
if [ "$result" -ne 0 ]; then
    printf '\nXem HUONG_DAN.txt de cai Python va FFmpeg.\n'
    printf 'Nhan Enter de dong...'
    read -r answer
fi
exit "$result"
