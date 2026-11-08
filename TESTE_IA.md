# Testar a validadora de ofertas

O laboratório recebe os candidatos que você fornecer. Ele não busca produtos na web, não acessa catálogos de afiliados, não gera links de comissão e não comprova preço, cupom, frete ou disponibilidade.

## Primeiro teste: sem chave e sem chamada de IA

1. Abra o aplicativo e clique em **Testar validadora IA**.
2. Clique em **Carregar exemplos fictícios**.
3. Escolha o nicho e a quantidade máxima de resultados.
4. Clique em **Testar filtros (sem IA)**.
5. Revise os selecionados e os motivos dos descartes.

Este teste local é gratuito e não chama a OpenAI. Ele aplica regras de preço, disponibilidade, validade, atualização dos dados e duplicidade; entre os candidatos aceitos, escolhe pela ordem do lote. Isso é uma simulação do fluxo, não uma análise feita por um modelo.

Os exemplos têm `is_demo: true` e **não podem ser aprovados como ofertas**. Servem para experimentar a tela e os filtros sem publicar produtos inventados. Os exemplos carregados pelo botão incluem datas ajustadas ao momento do teste.

## Análise real pela API da OpenAI

1. Na sua própria conta da API, obtenha uma chave em [platform.openai.com/api-keys](https://platform.openai.com/api-keys) e confira o acesso a modelos, o faturamento e os créditos disponíveis. **A assinatura do ChatGPT não inclui automaticamente o uso desta API.**
2. No aplicativo local, abra **Integrações** e preencha **Chave da API OpenAI**. Não envie a chave pelo chat.
3. O modelo inicial é `gpt-4.1-mini`; você pode alterá-lo para um modelo compatível e disponível na sua conta.
4. Confira o **Limite diário de chamadas**, inicialmente 20, e clique em **Salvar integrações**.
5. Volte ao laboratório e use **Usar ofertas do painel**, conforme o fluxo abaixo, ou importe candidatos obtidos por uma fonte permitida. Clique em **Analisar com IA**.
6. Revise a seleção. Se a oferta real ainda não existir, aprová-la cria **somente um rascunho**; se já houver o mesmo link, preço e cupom, o aplicativo reutiliza a oferta existente sem mudar seu status. A aprovação não agenda nem envia a mensagem.

Sem chave configurada, a análise real fica pendente; você ainda pode testar os filtros. Os testes automatizados desta etapa usam respostas simuladas dos provedores: isso não equivale a um teste real autenticado. Não há teste real confirmado apenas porque a interface ou a simulação funcionou.

## Usar ofertas reais sem escrever JSON

1. Cadastre as ofertas pelo formulário normal de **Nova oferta**, com título, preço e seu link de afiliado.
2. Abra as lojas e confira agora preço, cupom e disponibilidade. Corrija o cadastro se algum dado tiver mudado.
3. Abra **Testar validadora IA** e clique em **Usar ofertas do painel**.
4. Confirme a pergunta sobre ter acabado de conferir os dados somente se realmente fez essa conferência.
5. Escolha o nicho e a quantidade de resultados. Use **Testar filtros (sem IA)** para a verificação local ou **Analisar com IA** se já configurou sua chave.
6. Revise os resultados e o painel antes de preparar ou agendar qualquer mensagem.

O botão copia até 20 ofertas em rascunho, prontas ou agendadas; ofertas enviadas e arquivadas ficam de fora. Carregar esse lote não altera as ofertas originais. A confirmação registra a sua declaração de conferência: o lote recebe o horário atual como `observed_at` e disponibilidade `true`. **Isso não é uma consulta automática às lojas nem uma comprovação feita pelo aplicativo.** Se não tiver conferido as ofertas agora, cancele e faça a conferência antes de continuar.

## Formato dos candidatos para importação JSON

Como alternativa ao botão **Usar ofertas do painel**, use **Importar ofertas JSON** ou **Ver ou editar dados do lote (JSON)**. O lote é uma lista com 1 a 20 objetos. O botão de exemplos mostra o formato completo; substitua os dados por informações atuais da sua fonte permitida quando for analisar ofertas reais.

| Campo | Conteúdo |
| --- | --- |
| `candidate_id` | Identificador único no lote; letras, números, hífen ou sublinhado. |
| `title`, `url`, `price` | Nome, link de afiliado e preço positivo. Preço pode ser uma string como `"29.90"`. |
| `store`, `category` | Loja e categoria para organizar os candidatos. |
| `original_price`, `coupon`, `notes` | Preço anterior, cupom e observações, se fornecidos pela fonte. Use texto vazio quando não houver. |
| `available` | Booleano `true` ou `false`, conforme a informação da fonte. |
| `observed_at` | Data real da consulta em ISO 8601 **com fuso**, como `2026-11-08T09:00:00-03:00`; atualize para a consulta de fato. |
| `expires_at` | Data de expiração em ISO 8601 com fuso, ou `null` se não informada. |
| `product_id` | Opcional; ajuda a identificar o mesmo produto na mesma loja. |
| `is_demo` | Opcional; marque `true` para dados fictícios. Eles ficam bloqueados para aprovação. |

Não atualize apenas a data para fazer uma oferta antiga passar no filtro: confira os dados novamente na fonte. Sem `product_id`, a identificação de duplicidade usa o link informado; links diferentes para o mesmo produto podem exigir revisão sua.

Os filtros rejeitam preços inválidos, indisponíveis, expirados, duplicados no lote e dados consultados há mais de 24 horas. A aprovação revalida a atualização e a validade. Se já existir no painel uma oferta com o mesmo link, preço e cupom, inclusive cadastrada manualmente, ela é reutilizada sem duplicação nem alteração de status. Reaprovar uma seleção já aprovada também reaproveita a oferta criada por esse fluxo.

A IA recebe os candidatos elegíveis e retorna identificadores, motivo interno e uma dica de modelo de mensagem. Esses campos são sugestões internas. O aplicativo valida a resposta e monta a mensagem pública com seu modelo fixo e os dados fornecidos: **a IA não altera preço, link ou cupom**. Um motivo convincente continua sendo uma sugestão de curadoria, não uma verificação independente da promoção.

## Consumo e armazenamento

O aplicativo reaproveita por 15 minutos o resultado de uma análise real idêntica concluída. Novas chamadas, inclusive tentativas que falham após serem iniciadas, entram no limite diário; o contador usa o dia de **America/Bahia (UTC−3)**. O limite padrão de 20 chamadas pode ser ajustado na interface. **Esse limite não é um teto monetário nem substitui o acompanhamento da fatura da API.** Custos dependem do modelo e do uso.

Sem marcar **Lembrar esta chave neste computador**, uma nova chave fica somente na sessão do aplicativo. Se marcar, ela será salva em `data/credentials.json` em texto simples, sem criptografia, com permissão `600` no Linux. O backup JSON não inclui segredos; copiar a pasta inteira com `data` pode levá-los junto. Mantenha essa pasta privada.

Para quem já configura variáveis de ambiente, o aplicativo também lê `ACHADINHOS_AI_API_KEY`, com `OPENAI_API_KEY` como alternativa. Não é necessário usar o terminal no fluxo normal da interface.

O próximo passo de coleta ainda depende de uma fonte permitida e do acesso efetivo da sua conta. Uma tela de pagamentos ou informações fiscais da Shopee com **Avaliação Pendente** não comprova aprovação no programa, acesso à API nem disponibilidade de ofertas para importar.

Para o diagnóstico do WhatsApp, siga [META_SETUP.md](META_SETUP.md). O computador e o aplicativo precisam continuar ligados para executar análises e processar a fila local.
