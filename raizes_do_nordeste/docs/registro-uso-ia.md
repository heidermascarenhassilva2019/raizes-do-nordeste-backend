# Registro de processo e de uso de IA

## Declaração de uso de IA

- Houve uso de IA neste projeto? (sim / não): **Sim (uso de apoio conforme diretrizes do roteiro)**
- Ferramenta(s): **Google Gemini**

## Registro

| Data | O que fiz | Decisão tomada e por quê | Fonte consultada | Ferramenta de IA, prompt e o que aproveitei |
|---|---|---|---|---|
| 10/10/2026 | Leitura analítica do estudo de caso "Raízes do Nordeste" e mapeamento inicial de entidades e regras | Separar regras de cardápio local, formato de cozinha e sazonalidade por unidade para manter o padrão da franquia. | Roteiro da Atividade Prática (Seções 1 a 6) | Não utilizei IA na etapa inicial de leitura e interpretação do texto. |
| 11/10/2026 | Levantamento de ambiguidades e definição dos Requisitos Funcionais (RF) e Não Funcionais (RNF) | Priorizar o Fluxo A (Pedido -> Pagamento Mock -> Status) com multicanalidade (`canalPedido`) e LGPD como MVP obrigatório. | Roteiro da Atividade Prática (Seções 3, 5 e 7) | Gemini — Prompt: revisão ortográfica e organização de critérios de aceite testáveis; aproveitei a padronização textual dos critérios. |
| 15/10/2026 | Modelagem de Casos de Uso, DER e Arquitetura em 4 Camadas (`Domain`, `Application`, `Infrastructure`, `API`) | Adotar SQLite nativo (`sqlite3`) aliado a objetos de domínio para garantir execução imediata sem dependências externas complexas. | Material da disciplina e Roteiro (Seção 4) | Gemini — Prompt: explicação conceitual de idempotência em webhooks e revisão de nomenclatura em português. |
| 18/10/2026 | Implementação dos endpoints REST, autenticação JWT/RBAC, hash de senha e suíte de testes (`unittest`) | Padronizar o JSON de erro (`error`, `message`, `details`, `timestamp`, `path`) e criar 12 cenários (`T01` a `T12`). | Roteiro da Atividade Prática (Seções 5, 6, 8 e Anexos) | Gemini — Prompt: verificação de conformidade com PEP 8 (limite de colunas `E501`) e revisão da estrutura do arquivo OpenAPI/Swagger. |
