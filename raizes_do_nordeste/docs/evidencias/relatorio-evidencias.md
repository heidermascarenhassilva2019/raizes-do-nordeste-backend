# Evidências de validação — Raízes do Nordeste

## Ambiente e execução
- Projeto: API back-end Raízes do Nordeste.
- Comando executado na raiz do projeto: `python3 -B -m unittest discover -s tests -v`.
- Resultado observado nesta execução: **12 testes executados (6 positivos e 6 negativos), todos aprovados (`OK`)**.
- Log integral: [`execucao-testes.txt`](execucao-testes.txt).

## Matriz de rastreabilidade dos testes (Seção 8.4 do Roteiro)

| ID | Cenário | Endpoint | Pré-condição | Entrada | Esperado (status + pontos do response) | Evidência (nome na coleção / teste) |
|---|---|---|---|---|---|---|
| **T01** *(Positivo)* | Login válido | `POST /auth/login` | Usuário `cliente1` cadastrado no seed | `{"email": "cliente1@raizes.com", "senha": "123"}` | `200 OK` + `accessToken`, `perfil: "CLIENTE"` | `1. Auth / T01 - Login válido` (`test_T01`) |
| **T02** *(Negativo)* | Acesso sem token | `GET /pedidos` | Sem cabeçalho `Authorization` | Sem header Bearer | `401 Unauthorized` + `error: "TOKEN_AUSENTE_OU_INVALIDO"` | `5. Cenários de Erro / T02` (`test_T02`) |
| **T03** *(Negativo)* | Perfil sem permissão | `GET /relatorios/vendas` | Logado como `GERENTE` (`funcionario3`) | Header Bearer de `GERENTE` | `403 Forbidden` + `error: "PERMISSAO_NEGADA"` | `5. Cenários de Erro / T03` (`test_T03`) |
| **T04** *(Negativo)* | Campo obrigatório ausente | `POST /pedidos` | Logado como `CLIENTE` | `{"id_unidade": 1, "canalPedido": "APP", "itens": []}` | `400 Bad Request` + `error: "ITENS_OBRIGATORIOS"`, `details` | `5. Cenários de Erro / T04` (`test_T04`) |
| **T05** *(Negativo)* | Formato ou quantidade inválida | `POST /pedidos` e `POST /auth/login` | Logado como `CLIENTE` | `quantidade: -2` ou `email` sem `@` | `400 Bad Request` + `error: "QUANTIDADE_INVALIDA"` / `"FORMATO_INVALIDO"` | `test_T05` |
| **T06** *(Positivo)* | Criar pedido válido e filtrar por canal (`canalPedido`) | `POST /pedidos` e `GET /pedidos?canalPedido=TOTEM` | Estoque disponível na Unidade 1 | `{"id_unidade": 1, "canalPedido": "TOTEM", "itens": [{"id_produto": 1, "quantidade": 2}]}` | `201 Created` (`pedidoId`, `canalPedido: "TOTEM"`) e `200 OK` na filtragem | `2. Cardápio e Pedidos / T06a e T06b` (`test_T06`) |
| **T07** *(Negativo)* | Pedido com unidade ou produto inexistente | `POST /pedidos` | Logado como `CLIENTE` | `id_unidade: 999` ou `id_produto: 999` | `404 Not Found` + `error: "UNIDADE_NAO_ENCONTRADA"` / `"PRODUTO_NAO_ENCONTRADO"` | `5. Cenários de Erro / T07` (`test_T07`) |
| **T08** *(Negativo)* | Pedido com estoque insuficiente | `POST /pedidos` | Saldo local = 30 unidades | `{"id_unidade": 1, "canalPedido": "APP", "itens": [{"id_produto": 1, "quantidade": 999}]}` | `409 Conflict` + `error: "ESTOQUE_INSUFICIENTE"`, `details` | `5. Cenários de Erro / T08` (`test_T08`) |
| **T09** *(Positivo)* | Pagamento mock aprovado e avanço de status na cozinha | `POST /pedidos/{id}/pagamentos` e `PATCH /pedidos/{id}/status` | Pedido em `AGUARDANDO_PAGAMENTO` | `{"dados_pagamento": {"token_pagamento": "tok_ok", "simularResultado": "SUCCESS"}}` | `200 OK` (`status: "APROVADO"`, `status_pedido: "CONFIRMADO"`) e avanço até `ENTREGUE` | `3. Pagamento Mock e Status / T09a e T09b` (`test_T09`) |
| **T10** *(Negativo)* | Pagamento mock recusado e bloqueio de preparo | `POST /pedidos/{id}/pagamentos` e `PATCH /pedidos/{id}/status` | Pedido em `AGUARDANDO_PAGAMENTO` | `{"dados_pagamento": {"simularResultado": "FAILURE"}}` + tentativa de `EM_PREPARO` | `200 OK` (`status: "RECUSADO"`) e `409 Conflict` ao tentar enviar para cozinha | `3. Pagamento Mock e Status / T10` (`test_T10`) |
| **T11** *(Positivo)* | Cancelamento auditado e anonimização LGPD | `POST /pedidos/{id}/cancelamento`, `POST /clientes/1/anonimizacao` e `GET /auditoria/logs` | Perfil `GERENTE` e `MATRIZ` | `{"motivo": "Cancelamento autorizado por funcionario3"}` | `200 OK` (`status: "CANCELADO"`, `anonimizado: true`) e logs em `/auditoria/logs` | `4. LGPD, Fidelidade, Auditoria e Matriz / T11a-c` (`test_T11`) |
| **T12** *(Positivo)* | Consulta de cardápio sazonal, fidelidade (CPF mascarado) e relatório Matriz | `GET /unidades/1/cardapio?mes=6`, `GET /clientes/1/fidelidade` e `GET /relatorios/vendas` | Perfis `CLIENTE` e `MATRIZ` | Query `?mes=6` | `200 OK` (4 produtos ativos em junho, CPF mascarado `***.456.789-**` e vendas por canal/unidade) | `4. LGPD, Fidelidade, Auditoria e Matriz / T12a-c` (`test_T12`) |
