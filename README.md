# Raízes do Nordeste
## API Back-end | Projeto Multidisciplinar

**Aluno:** Heider Mascarenhas  
**RU:** 5157680  
**Implementação:** Python 3 (biblioteca padrão + SQLite relacional nativo)  
**Porta HTTP:** `8000`

## 1. Visão geral

O projeto implementa uma API HTTP RESTful para demonstrar as operações da rede **Raízes do Nordeste**: consulta de cardápio por unidade, criação e listagem de pedidos multicanal (`canalPedido`), controle de estoque local, simulação de pagamentos externos com idempotência e webhook, programa de fidelização, conformidade com a LGPD (hash de senha, mascaramento de CPF, consentimento explícito e anonimização), trilha de auditoria e relatório consolidado de vendas para a Matriz.

## 2. Tecnologias e Persistência

| Tecnologia | Uso no Projeto |
|---|---|
| Python 3 (`http.server`, `json`, `urllib.parse`) | Servidor HTTP REST e serialização de contratos JSON |
| `sqlite3` (Banco Relacional Nativo) | Persistência relacional com *migrations* e *seed* automático (`unidades`, `produtos`, `estoques_unidade`, `clientes`, `pedidos`, `logs_auditoria`) |
| `hashlib` / `hmac` | Hash seguro de senhas (SHA-256 com *salt*) e assinatura de tokens JWT |
| `unittest` | Suíte de testes automatizados com 12 cenários (`T01` a `T12`) |
| OpenAPI 3.0.3 (`swagger_openapi.yaml`) | Documentação formal dos contratos de API |
| Postman Collection v2.1 | Coleção organizada em 5 pastas para validação executável |

## 3. Como Configurar e Executar (Passo a Passo)

1. **Configurar variáveis de ambiente:**
   Copie o arquivo `.env.example` para `.env` (opcional, pois a aplicação possui valores padrão seguros):
   ```bash
   cp .env.example .env
   ```
2. **Criar banco, executar migrations e seed:**
   Ao iniciar a aplicação ou rodar os testes, o `RepositorioBD` executa automaticamente as *migrations* SQL (`CREATE TABLE IF NOT EXISTS`) e aplica o *seed* inicial das unidades, produtos, estoques e clientes.
3. **Iniciar a API:**
   ```bash
   python3 -m src.main
   ```
   A API ficará disponível em `http://localhost:8000`.
4. **Executar os 12 testes automatizados:**
   ```bash
   python3 -B -m unittest discover -s tests -v
   ```

## 4. Endpoints Implementados

| Método | Rota | Autenticação / Perfil | Finalidade |
|---|---|---|---|
| `POST` | `/auth/login` | Público | Autentica usuário (validando hash de senha) e retorna token JWT |
| `GET` | `/unidades` | Público | Lista as unidades cadastradas na rede |
| `GET` | `/unidades/{id}/cardapio?mes={n}` | Público | Lista o cardápio ativo filtrando estoque, cozinha e sazonalidade |
| `PATCH` | `/unidades/{id}/estoque/{produtoId}` | JWT (`GERENTE`, `MATRIZ`) | Movimenta estoque local (entrada/saída) com registro em auditoria |
| `POST` | `/pedidos` | JWT (`CLIENTE`, `ATENDENTE`, `GERENTE`, `MATRIZ`) | Cria pedido multicanal exigindo `canalPedido` e validando estoque |
| `GET` | `/pedidos?canalPedido={c}&status={s}&page=1&limit=10` | JWT (Autenticado) | Lista e filtra pedidos por canal de origem e status com paginação |
| `GET` | `/pedidos/{id}` e `/pedidos/{id}/status` | Público / Loja | Consulta detalhes ou status em tempo real do pedido |
| `POST` | `/pedidos/{id}/pagamentos` | Header `Idempotency-Key` | Solicita cobrança ao gateway simulado (`SUCCESS`, `FAILURE`, `PENDENTE`) |
| `POST` | `/pagamentos/webhook` | Público (Callback Gateway) | Processa confirmação/recusa assíncrona do gateway |
| `PATCH` | `/pedidos/{id}/status` | JWT (`COZINHEIRO`, `ATENDENTE`, `GERENTE`, `MATRIZ`) | Avança status do pedido (`EM_PREPARO` -> `PRONTO` -> `ENTREGUE`) |
| `POST` | `/pedidos/{id}/cancelamento` | JWT (`GERENTE`, `MATRIZ`) | Cancela pedido com justificativa obrigatória, estorna estoque e audita |
| `POST` | `/clientes/{id}/consentimentos` | Público / Cliente | Registra termo de consentimento explícito (*opt-in* LGPD) |
| `GET` | `/clientes/{id}/fidelidade` | JWT (`CLIENTE`, `ATENDENTE`, `GERENTE`, `MATRIZ`) | Consulta saldo de pontos com CPF mascarado e grava log de acesso |
| `POST` | `/clientes/{id}/anonimizacao` | JWT (`CLIENTE`, `GERENTE`, `MATRIZ`) | Anonimiza dados pessoais do titular mantendo histórico contábil |
| `GET` | `/relatorios/vendas` | JWT (`MATRIZ`) | Relatório consolidado de vendas por unidade, por canal e top produtos |
| `GET` | `/auditoria/logs` | JWT (`MATRIZ`, `GERENTE`) | Consulta trilha imutável de auditoria de operações sensíveis |

## 5. Plano de Testes (12 Cenários: 6 Positivos e 6 Negativos)

Veja o detalhamento completo em [`docs/evidencias/relatorio-evidencias.md`](docs/evidencias/relatorio-evidencias.md) e o log de execução em [`docs/evidencias/execucao-testes.txt`](docs/evidencias/execucao-testes.txt).
