#!/usr/bin/env bash
cd -- "$(dirname -- "$0")" || exit 1
python3 tunnel.py
achadinhos_status=$?
if [[ $achadinhos_status -ne 0 && -t 0 ]]; then
  read -r -p "Pressione Enter para fechar... " achadinhos_reply
fi
exit "$achadinhos_status"
