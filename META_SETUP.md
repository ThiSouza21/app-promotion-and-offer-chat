# Configurar o diagnóstico da Meta

Esta etapa verifica se um token consegue ler os dados de um número na API oficial do WhatsApp. **Ela não envia mensagens, não configura webhooks ou modelos de mensagem e não confirma acesso a grupos ou comunidades.** O envio atual continua manual pelo WhatsApp.

## Na sua conta da Meta

1. Abra [developers.facebook.com/apps/](https://developers.facebook.com/apps/) no seu navegador e faça login na sua própria conta. Não compartilhe sua senha ou token pelo chat.
2. Crie um aplicativo ou abra o aplicativo que usará para o projeto. Adicione o produto **WhatsApp** conforme o fluxo oferecido pela Meta.
3. Procure **API Setup**, **Configuração da API** ou a seção equivalente. Os nomes e as exigências podem variar no fluxo atual.
4. Se a Meta oferecer um número de teste, prefira usá-lo nesta primeira validação antes de vincular um número real.
5. Localize o **token de acesso** e o **Phone Number ID / ID do número de telefone**. Esse ID é um identificador exibido pela Meta, **não é o número de celular com DDD**. O token precisa estar válido e ter acesso ao número escolhido.

Esses passos são uma orientação geral. A documentação atual da Meta não pôde ser consultada nesta sessão; confira os requisitos que aparecerem na sua conta. Não há promessa de gratuidade, preços, aprovação de conta ou compatibilidade com comunidades/grupos.

## No aplicativo Achadinhos

1. Abra **Integrações**.
2. Em **WhatsApp · Diagnóstico da Meta**, cole o **Token de acesso da Meta** no campo protegido.
3. Preencha **ID do número de telefone** com o identificador obtido na Meta.
4. Confira **Versão da Graph API**. O valor inicial do aplicativo é `v23.0`, configurável; use uma versão que esteja suportada para sua configuração na Meta. Esse padrão não é uma confirmação de versão atual.
5. Clique em **Salvar e testar conexão Meta**.

Por padrão, um novo token fica somente na sessão do aplicativo. Marcar **Lembrar este token neste computador** salva o token em texto simples em `data/credentials.json`, sem criptografia, com permissão `600` no Linux. Ele não entra no backup JSON, mas pode ser levado ao copiar a pasta inteira com `data`. Use **Esquecer token local** para remover o segredo guardado pelo aplicativo; isso não revoga o token na Meta.

Como alternativa para quem já usa variáveis de ambiente, são aceitas `ACHADINHOS_META_TOKEN` e, como opção alternativa, `WHATSAPP_ACCESS_TOKEN`. O uso normal pode ser feito pelos campos da interface, sem comandos.

## O que o teste comprova

O aplicativo faz apenas esta leitura, usando o token no cabeçalho da requisição:

```text
GET https://graph.facebook.com/{versao}/{phone_number_id}?fields=id,display_phone_number,verified_name,quality_rating
```

Uma resposta válida confirma o acesso aos dados daquele número. Ela não comprova permissão de envio, entrega de mensagens, cadastro de destinatários, funcionamento de webhooks ou acesso ao destino desejado. Se falhar, confira a mensagem apresentada, a validade e as permissões do token, o ID e a versão configurada. Uma resposta simulada em teste automatizado não estabelece conexão real com a Meta.

## Situação do ambiente de desenvolvimento

**A conta da Meta não foi aberta nem alterada nesta sessão.** O login, a criação do aplicativo e a obtenção do token devem acontecer na sua própria conta. Liberar destinos e declarar requisitos no ambiente de desenvolvimento não executa essas ações dentro da Meta e não cria credenciais.

Neste ambiente, as tentativas HTTP à documentação da Meta foram bloqueadas pelo proxy com `403 CONNECT`. Foram salvos no rascunho os destinos `developers.facebook.com`, `graph.facebook.com` e `api.openai.com`, e requisitos de credenciais com os nomes `ACHADINHOS_META_TOKEN` e `ACHADINHOS_AI_API_KEY`, sem valores. O rascunho ainda não havia sido aplicado à instância: salvar uma proposta não comprova acesso à rede nem autenticação. Os valores devem ser fornecidos por configuração protegida, nunca no chat. Após aplicar as configurações, será necessário repetir a operação afetada para validar o acesso.

O ambiente informa suporte a desktop remoto, mas o estado estava desconhecido e as ferramentas de navegador compartilhado `cua_repl.js` / `open_in_codex` não estavam disponíveis. Não foi possível usar esse navegador para fazer o login. Não há teste real autenticado confirmado da Meta ou da OpenAI nesta etapa.

Identificador do ambiente para diagnóstico:

```text
ccarenv_b64_Y2NhcmVudl8wYWIyOWIyMjA3OTA4MTkxODY3ZTA4YzMyYWVmMTQ3ZA
```

O anexo da Shopee mostrava a área de pagamentos/informações fiscais com **Avaliação Pendente**. Essa tela não confirma aprovação de afiliação, acesso a uma API ou uma fonte de ofertas; essa configuração é separada da Meta.
