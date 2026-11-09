# Webhooks do Oásis das Promos

O receptor verifica o callback da Meta e registra mensagens recebidas e status de entrega. Receber um “oi” não dispara resposta automática. Não há envio de campanhas implementado.

## No KDE Neon

1. Feche a versão anterior e abra a nova por **Abrir Achadinhos.desktop**. Preserve a pasta `data` ao atualizar.
2. Abra **Webhooks** no painel.
3. Na Meta, em **Configurações do app → Básico**, obtenha a **chave secreta do app**. Informe-a somente no campo protegido **Chave secreta do app Meta** do nosso painel e salve. Ela valida a assinatura dos eventos e é diferente do token de acesso da API.
4. Abra **Abrir Webhook HTTPS.desktop**. Permita execução se o Dolphin solicitar. Na primeira abertura, ele baixa o conector oficial Cloudflare 2026.10.7 e confere o SHA-256 publicado na release antes de executar. O binário fica em `tools/`, sem instalação global. Suporta Linux x86_64 e ARM64.
5. Mantenha o aplicativo e o túnel abertos. No painel, clique em **Atualizar eventos e URL**.
6. Copie a URL pública terminada em `/webhooks/whatsapp` para **URL de callback** na Meta. Não use localhost nem a porta do painel.
7. Clique em **Copiar token de verificação** e cole em **Verificar token** na Meta. Esse token é gerado pelo nosso app; não é o token de acesso da API nem a chave secreta do app.
8. Na Meta, clique em **Verificar e salvar** e assine o campo **messages** do objeto WhatsApp correspondente à conta. A assinatura da conta/app e os requisitos de permissões/publicação exibidos pela Meta também precisam estar atendidos. Não há assinatura remota automática no app.
9. Teste com a ferramenta de webhook da Meta ou envie um “oi” ao número configurado. Os eventos aparecem em **Webhooks** e a tela atualiza a cada 10segundos. O teste do painel confirma o caminho de teste; só um evento real confirma a integração da conta.

O túnel gratuito de teste é temporário e não garante disponibilidade. O endereço muda ao reiniciar: atualize e verifique novamente o callback na Meta. Para produção contínua, use endereço HTTPS fixo com túnel nomeado ou servidor. Para o protótipo não é necessário contratar servidor, mas o computador e os dois processos precisam estar ligados. O app não garante recuperar todos os eventos de longos períodos offline.

## Isolamento e dados locais

- Painel `127.0.0.1:8765`: nunca expor no túnel.
- Receptor `127.0.0.1:8766`: aceita apenas `/webhooks/whatsapp`; outros caminhos retornam 404. O iniciador descobre a porta efetiva e encaminha somente esse receptor.
- GET valida token e devolve o challenge numérico. POST verifica `X-Hub-Signature-256` com HMAC-SHA256 sobre o corpo original. Sem chave configurada, recusa eventos com 503; assinatura incorreta retorna 403.
- Confirma com 200 somente após gravar; eventos repetidos são ignorados. Falha de persistência retorna 503 para permitir nova tentativa. Limite de 2 MB por corpo.
- Exibe até 50 eventos recentes: recebida, enviada, entregue, lida, falha e erro associado. Não baixa mídia nem envia resposta ao remetente.

Credenciais em `data/webhook_credentials.json`, permissão 600 no Linux, texto simples sem criptografia. Histórico no SQLite local. Backup JSON de ofertas não inclui esses segredos ou eventos; copiar `data` inteira leva ambos. Mantenha a pasta privada. Não envie tokens/chaves pelo chat ou em HTMLs.

## Restrição 130497

Os logs do usuário comprovam falha 130497 ao enviar do número de teste +1 para seu destinatário brasileiro. A resposta compartilhada de um BSP é compatível com restrição internacional, mas não determina a causa administrativa desta conta. Os limiares citados pelo BSP não foram confirmados aqui. Registrar um número +55 pode ser o próximo teste adequado, sujeito às exigências da Meta; não garante entrega nem acesso a comunidades/grupos. Webhooks observam a falha e não removem a restrição.

Ao registrar o número +55 reservado, atualize Phone Number ID/token em **Integrações**. Modelos, envio e elegibilidade do destino continuam sendo etapas separadas.

## Validação e diagnóstico

O receptor foi testado localmente com eventos assinados simulados, incluindo falhas130497. O conector oficial foi baixado, teve SHA-256 conferido e `--version` executado. O túnel real nesta nuvem falhou por resolução DNS de `api.trycloudflare.com`, antes de gerar URL. Não houve callback real da Meta nesta sessão. Essa falha não diagnostica a rede do seu computador.

Uso avançado: `python3 app.py --no-browser --webhook-port 8766`. Com outra `--port`, o padrão é uma porta efêmera de webhook para testes isolados. `python3 tunnel.py --app-port PORT --data-dir PASTA` permite outra instância. Para túnel de terceiros, encaminhe somente a porta do receptor, nunca o painel.
