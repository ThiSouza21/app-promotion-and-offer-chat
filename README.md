# Achadinhos

Organize ofertas de afiliado no seu computador, prepare mensagens e retome sua fila quando ligar o aplicativo novamente. O uso básico é local, sem mensalidade de servidor nem dependências para instalar com `pip` ou `npm`. A análise opcional por IA usa uma API que pode ter cobrança.

**Nesta versão, você revisa e envia as mensagens no WhatsApp.** O aplicativo não envia sozinho, não consulta preços nas lojas e não gera links de afiliado. Use os links obtidos no seu programa de afiliados e confira se a divulgação naquele canal é permitida.

## Primeira abertura

1. Baixe este repositório como ZIP e **extraia todos os arquivos** para uma pasta fixa do computador. Não abra o iniciador de dentro do ZIP.
2. É necessário **Python 3.10 ou mais recente**. No KDE Neon, o Python 3 normalmente já está instalado; se precisar, use o gerenciador de programas da distribuição. Para outros sistemas, use o [download oficial](https://www.python.org/downloads/). No Windows, marque **Add Python to PATH** no instalador.
3. Abra o iniciador do seu sistema:

| Sistema | Arquivo |
| --- | --- |
| Linux / KDE Neon | Dê dois cliques em `Abrir Achadinhos.desktop`, dentro da pasta do aplicativo. |
| Windows | Dê dois cliques em `Iniciar no Windows.bat`. |
| macOS | Abra `Iniciar no Mac.command`. |

O aplicativo abre no navegador. Mantenha a janela do iniciador aberta enquanto estiver usando a fila; ela pode ficar minimizada. No dia a dia, basta abrir o mesmo arquivo novamente. No Dolphin, a primeira abertura pode pedir **Marcar como confiável** ou **Permitir executar**; nas propriedades do arquivo, em **Permissões**, permita a execução se necessário. Como alternativa, abra `Iniciar no Linux.sh` com **Executar no terminal**.

No macOS, a primeira abertura pode exigir **Abrir** pelo botão direito ou autorização nas configurações de segurança. ZIPs podem perder a permissão de execução no macOS e Linux: se necessário, marque o arquivo como executável nas propriedades; no macOS, um ajuste único pelo Terminal é `chmod +x "Iniciar no Mac.command"`, dentro da pasta extraída. No Linux, a opção de executar scripts depende do gerenciador de arquivos.

## Levar para outro computador com KDE Neon / Linux

Feche o aplicativo antes de copiar e leve **a pasta inteira**, incluindo `data`, para o outro computador. Abra o arquivo `Abrir Achadinhos.desktop` dentro da nova pasta; ele encontra o aplicativo pela própria localização, sem caminhos fixos. É necessário ter Python 3.10+ e um navegador no destino. Não copie somente o atalho para outra pasta: ele deve ficar junto dos demais arquivos. Um atalho simbólico do KDE pode apontar para esse arquivo se quiser acessá-lo pela área de trabalho.

A cópia leva suas ofertas e configurações. **Se você tiver marcado “Lembrar” nas integrações, ela também leva as chaves e os tokens salvos em `data/credentials.json`.** Esse arquivo não é criptografado: mantenha a pasta privada. O backup JSON transporta ofertas sem copiar esses segredos. Cada computador passa a ter uma cópia independente; não há sincronização automática. Ao usar pendrive, prefira copiar a pasta para o computador antes de iniciar.

## Como usar

1. Cadastre o produto, o preço que você conferiu e seu link de afiliado. Cupom, categoria e observações são opcionais.
2. Salve um rascunho, prepare a mensagem agora ou escolha um horário para ela ficar pronta.
3. Revise a mensagem e use **Copiar** ou **Abrir WhatsApp**. Escolha o destino e confirme o envio no WhatsApp.
4. Volte ao aplicativo e marque a oferta como enviada. Abrir o WhatsApp ou copiar o texto não significa que a mensagem foi enviada.

Preço, frete, cupom e validade precisam ser conferidos por você. Uma mensagem preparada não garante que a promoção continue disponível. Ainda não há busca automática em lojas, integração com catálogos de afiliados ou envio pela API do WhatsApp.

## Receber webhooks do WhatsApp

O botão **Webhooks** permite configurar a chave secreta do app, copiar o token de verificação e acompanhar mensagens recebidas/status. Abra **Abrir Webhook HTTPS.desktop** para expor somente o receptor por HTTPS. Veja o passo a passo e as limitações em [WEBHOOKS.md](WEBHOOKS.md). Não há resposta automática nem envio de campanhas.

## Testar a IA e configurar integrações

- **Testar validadora IA** abre um laboratório para filtrar e revisar até 20 candidatos. Comece por **Carregar exemplos fictícios** e **Testar filtros (sem IA)**: não exige chave, não chama a OpenAI e não consome créditos de IA. Os exemplos não podem virar ofertas. Para testar suas próprias ofertas sem escrever JSON, cadastre-as pelo formulário normal, confira os dados nas lojas e clique em **Usar ofertas do painel** no laboratório. Confirme a conferência apenas depois de fazê-la; o aplicativo não consulta as lojas.
- **Analisar com IA** usa a API da OpenAI configurada em **Integrações**. O modelo inicial é `gpt-4.1-mini`, configurável conforme o acesso da conta. A assinatura do ChatGPT é separada do uso da API. A IA trabalha com os dados fornecidos; não pesquisa na internet nem comprova promoções. Aprovar um candidato real adiciona um rascunho se a oferta ainda não existir; se já houver o mesmo link, preço e cupom, reutiliza a oferta existente sem mudar seu status.
- **Integrações** também permite configurar e testar o acesso a um número da API da Meta. O teste apenas lê dados do número; não envia mensagens nem confirma suporte a comunidades ou grupos.

Veja o passo a passo em [TESTE_IA.md](TESTE_IA.md) e [META_SETUP.md](META_SETUP.md). O teste de filtros e os testes automatizados com respostas simuladas não comprovam uma conexão real com os provedores.

As chaves e os tokens são informados em campos protegidos da interface. Por padrão, os novos segredos ficam apenas na sessão do aplicativo. Marcar **Lembrar** salva o segredo em texto simples em `data/credentials.json`, com permissão restrita no Linux, sem criptografia. Eles não entram no backup JSON. Não envie esses dados pelo chat nem os coloque nos candidatos.

## Ao desligar e ligar o computador

Com o computador desligado ou o aplicativo fechado, a fila não é processada. Quando abrir o iniciador novamente, as ofertas continuam salvas e os agendamentos vencidos ficam **prontos para revisão**, sem enviar mensagens acumuladas automaticamente. Você pode fechar a aba do navegador e reabri-la pelo endereço mostrado no iniciador; fechar a janela do iniciador encerra o aplicativo.

Os dados ficam em `data/achadinhos.sqlite3`, dentro da pasta do projeto. Não apague essa pasta. Para fazer uma cópia de segurança, use a opção de backup da interface e guarde o arquivo JSON em outro local. A importação mescla as ofertas, sem substituir aquelas que já existem com o mesmo identificador. Antes de mover ou reinstalar o aplicativo, faça um backup.

O painel comporta até 5.000 ofertas, contando as arquivadas. O backup JSON transporta as ofertas; a importação preserva o nome do canal configurado no computador de destino. Para levar também essa configuração, copie a pasta inteira com o aplicativo fechado. Se outra cópia já estiver aberta no mesmo computador, feche-a antes de iniciar a pasta nova.

O uso básico funciona localmente. A internet é necessária para acessar o WhatsApp e as lojas no navegador, analisar com IA ou testar a conexão Meta. O aplicativo não pede sua senha do WhatsApp nem credenciais de afiliado; os campos de integração recebem somente a chave da API OpenAI e o token da Meta.

## Para desenvolvimento

Requer Python 3.10+. Não há instalação de pacotes externos.

```sh
python3 app.py --no-browser
python3 -m unittest discover -s tests -v
```

No Windows, use `py -3` no lugar de `python3`. Por padrão, o serviço usa `127.0.0.1:8765` e guarda os dados na pasta `data`. Há opções `--host`, `--port`, `--no-browser` e `--data-dir`.
