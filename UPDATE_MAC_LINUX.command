#!/bin/sh
cd "$(dirname "$0")" || exit 1
printf 'Cap nhat Review Studio tu GitHub (chi tai cac file thay doi)...\n'
python3 update.py
printf 'Nhan Enter de dong...'
read -r answer
