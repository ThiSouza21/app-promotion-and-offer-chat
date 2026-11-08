#!/usr/bin/env bash

# Inicie pelo gerenciador de arquivos com a opcao "Executar no terminal".
cd -- "$(dirname -- "$0")" || exit 1

pause_on_error() {
  if [[ -t 0 ]]; then
    read -r -p "Pressione Enter para fechar... " achadinhos_reply
  fi
}

if ! command -v python3 >/dev/null 2>&1 ||
   ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
  echo "Instale o Python 3.10 ou mais recente pelo gerenciador de programas da sua distribuicao."
  echo "Depois, abra este arquivo novamente. Nao e necessario instalar pacotes com pip."
  pause_on_error
  exit 1
fi

python3 app.py
achadinhos_status=$?
if [[ $achadinhos_status -ne 0 && $achadinhos_status -ne 130 ]]; then
  echo "O aplicativo nao conseguiu iniciar. Leia a mensagem acima."
  pause_on_error
fi
exit "$achadinhos_status"
