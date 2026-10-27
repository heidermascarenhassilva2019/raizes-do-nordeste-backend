from datetime import datetime, timezone
from typing import Optional
import uuid
from src.application.use_cases import ControladorCasoDeUso
from src.domain.entities import ErroRegraDeNegocio
from src.infrastructure.repositories_and_services import ServicoAutenticacao


class ControladorAPI:
    """Camada 1 (API): Recebe chamadas HTTP, valida Auth e delega."""

    def __init__(self, servico_aplicacao: ControladorCasoDeUso):
        self.app = servico_aplicacao

    @staticmethod
    def _formatar_erro_padrao(
        codigo_erro: str,
        mensagem: str,
        caminho: str,
        detalhes: Optional[list] = None,
    ) -> dict:
        agora_iso = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        return {
            "error": codigo_erro,
            "message": mensagem,
            "erro": mensagem,
            "details": detalhes or [],
            "timestamp": agora_iso,
            "path": caminho,
            "requestId": str(uuid.uuid4()),
        }

    def processar_requisicao(
        self,
        metodo: str,
        caminho: str,
        headers: Optional[dict] = None,
        body: Optional[dict] = None,
        query: Optional[dict] = None,
    ) -> tuple:
        headers = headers or {}
        body = body or {}
        query = query or {}
        cabecalho_autorizacao = headers.get("Authorization", "")
        token_jwt = (
            cabecalho_autorizacao.replace("Bearer ", "")
            if cabecalho_autorizacao
            else None
        )

        try:
            # POST /auth/login
            if metodo == "POST" and caminho == "/auth/login":
                resposta_login = ServicoAutenticacao.autenticar_login(
                    body.get("email", ""), body.get("senha", "")
                )
                return 200, resposta_login

            # GET /unidades (Listagem de unidades da rede)
            if metodo == "GET" and caminho == "/unidades":
                unidades_lista = [
                    vars(u) for u in self.app.db.unidades.values()
                ]
                return 200, {"total": len(unidades_lista), "dados": unidades_lista}

            # GET /unidades/{id}/cardapio
            if (
                metodo == "GET"
                and caminho.startswith("/unidades/")
                and caminho.endswith("/cardapio")
            ):
                id_unidade = int(caminho.split("/")[2])
                mes_consulta = int(query.get("mes", 10))
                itens_cardapio = self.app.listar_cardapio_unidade(
                    id_unidade, mes_atual=mes_consulta
                )
                return 200, {"status": "sucesso", "dados": itens_cardapio}

            # PATCH /unidades/{id}/estoque/{produtoId}
            if (
                metodo == "PATCH"
                and caminho.startswith("/unidades/")
                and "/estoque/" in caminho
            ):
                partes = caminho.split("/")
                id_unidade = int(partes[2])
                id_produto = int(partes[4])
                usuario_aut = ServicoAutenticacao.validar_token(
                    token_jwt, perfis_permitidos=["GERENTE", "MATRIZ"]
                )
                res_estoque = self.app.movimentar_estoque_unidade(
                    id_unidade=id_unidade,
                    id_produto=id_produto,
                    quantidade_ajuste=int(body.get("quantidade_ajuste", 0)),
                    usuario_autenticado=usuario_aut,
                    motivo=body.get("motivo", "Ajuste operacional de estoque"),
                )
                return 200, res_estoque

            # GET /pedidos (Multicanalidade: filtro ?canalPedido=TOTEM&status=...&page=1&limit=10)
            if metodo == "GET" and caminho == "/pedidos":
                ServicoAutenticacao.validar_token(
                    token_jwt,
                    perfis_permitidos=[
                        "CLIENTE",
                        "ATENDENTE",
                        "COZINHEIRO",
                        "GERENTE",
                        "MATRIZ",
                    ],
                )
                canal_filtro = query.get("canalPedido") or query.get("canal")
                status_filtro = query.get("status")
                pagina = int(query.get("page", 1))
                limite = int(query.get("limit", 10))
                listagem = self.app.listar_pedidos(
                    canal_pedido=canal_filtro,
                    status=status_filtro,
                    page=pagina,
                    limit=limite,
                )
                return 200, listagem

            # GET /pedidos/{id} e GET /pedidos/{id}/status
            if metodo == "GET" and caminho.startswith("/pedidos/"):
                partes = [p for p in caminho.split("/") if p]
                id_pedido = int(partes[1])
                dados_ped = self.app.consultar_pedido_por_id(id_pedido)
                if len(partes) == 3 and partes[2] == "status":
                    return 200, {
                        "pedidoId": dados_ped["pedidoId"],
                        "canalPedido": dados_ped["canalPedido"],
                        "status": dados_ped["status"],
                    }
                return 200, dados_ped

            # POST /pedidos
            if metodo == "POST" and caminho == "/pedidos":
                if token_jwt:
                    perfis_autorizados = [
                        "CLIENTE",
                        "ATENDENTE",
                        "GERENTE",
                        "MATRIZ",
                    ]
                    ServicoAutenticacao.validar_token(
                        token_jwt, perfis_permitidos=perfis_autorizados
                    )
                canal_pedido = (
                    body.get("canalPedido") or body.get("canal", "")
                )
                id_unidade = body.get("unidadeId") or body.get("id_unidade")
                if not id_unidade:
                    mensagem_erro = (
                        "O campo 'id_unidade' (ou 'unidadeId') é obrigatório."
                    )
                    return 400, self._formatar_erro_padrao(
                        "CAMPO_OBRIGATORIO_AUSENTE",
                        mensagem_erro,
                        caminho,
                        [{"field": "id_unidade", "issue": "Campo obrigatório"}],
                    )
                pedido_criado = self.app.criar_pedido(
                    id_unidade=int(id_unidade),
                    canal_atendimento=canal_pedido,
                    itens_solicitados=body.get("itens", []),
                    id_cliente=(
                        body.get("clienteId") or body.get("id_cliente")
                    ),
                    mes_atual=body.get("mes_atual", 10),
                    hora_atual=body.get("hora_atual", 14),
                )
                return 201, {
                    "status": "criado",
                    "pedidoId": pedido_criado.id,
                    "id_pedido": pedido_criado.id,
                    "canalPedido": pedido_criado.canal,
                    "valor_total": pedido_criado.valor_total,
                    "valor_desconto": pedido_criado.valor_desconto,
                    "status_pedido": pedido_criado.status,
                    "createdAt": pedido_criado.criado_em,
                }

            # POST /pedidos/{id}/pagamentos
            if (
                metodo == "POST"
                and caminho.startswith("/pedidos/")
                and caminho.endswith("/pagamentos")
            ):
                id_pedido = int(caminho.split("/")[2])
                chave_padrao = f"idempotencia-pedido-{id_pedido}"
                chave_idempotencia = headers.get(
                    "Idempotency-Key",
                    body.get("chave_idempotencia", chave_padrao),
                )
                resposta_pagamento = self.app.solicitar_pagamento(
                    id_pedido,
                    chave_idempotencia,
                    body.get("dados_pagamento", {}),
                )
                return 200, resposta_pagamento

            # POST /pagamentos/webhook
            if metodo == "POST" and caminho == "/pagamentos/webhook":
                resposta_webhook = self.app.processar_webhook_pagamento(
                    body["id_pagamento"],
                    body["id_transacao_externa"],
                    body["resultado"],
                )
                return 200, resposta_webhook

            # PATCH /pedidos/{id}/status
            if (
                metodo == "PATCH"
                and caminho.startswith("/pedidos/")
                and caminho.endswith("/status")
            ):
                perfis_operacionais = [
                    "COZINHEIRO",
                    "ATENDENTE",
                    "GERENTE",
                    "MATRIZ",
                ]
                usuario_aut = ServicoAutenticacao.validar_token(
                    token_jwt, perfis_permitidos=perfis_operacionais
                )
                id_pedido = int(caminho.split("/")[2])
                pedido_atualizado = self.app.atualizar_status_pedido(
                    id_pedido,
                    body["novo_status"],
                    usuario_autenticado=usuario_aut,
                )
                return 200, {
                    "pedidoId": pedido_atualizado.id,
                    "id_pedido": pedido_atualizado.id,
                    "status": pedido_atualizado.status,
                }

            # POST /pedidos/{id}/cancelamento
            if (
                metodo == "POST"
                and caminho.startswith("/pedidos/")
                and caminho.endswith("/cancelamento")
            ):
                usuario_autorizador = ServicoAutenticacao.validar_token(
                    token_jwt, perfis_permitidos=["GERENTE", "MATRIZ"]
                )
                id_pedido = int(caminho.split("/")[2])
                pedido_cancelado = self.app.cancelar_pedido_auditado(
                    id_pedido, usuario_autorizador, body.get("motivo", "")
                )
                return 200, {
                    "pedidoId": pedido_cancelado.id,
                    "id_pedido": pedido_cancelado.id,
                    "status": pedido_cancelado.status,
                }

            # POST /clientes/{id}/consentimentos
            if (
                metodo == "POST"
                and caminho.startswith("/clientes/")
                and caminho.endswith("/consentimentos")
            ):
                id_cliente = int(caminho.split("/")[2])
                cliente_atualizado = self.app.registrar_consentimento_lgpd(
                    id_cliente, body.get("aceito", False)
                )
                return 200, {
                    "id_cliente": cliente_atualizado.id,
                    "consentimento_lgpd": (
                        cliente_atualizado.consentimento_lgpd
                    ),
                }

            # GET /clientes/{id}/fidelidade
            if (
                metodo == "GET"
                and caminho.startswith("/clientes/")
                and caminho.endswith("/fidelidade")
            ):
                perfis_autorizados = [
                    "CLIENTE",
                    "ATENDENTE",
                    "GERENTE",
                    "MATRIZ",
                ]
                usuario_autenticado = ServicoAutenticacao.validar_token(
                    token_jwt, perfis_permitidos=perfis_autorizados
                )
                id_cliente = int(caminho.split("/")[2])
                extrato_fidelidade = self.app.consultar_perfil_fidelidade(
                    id_cliente, usuario_autenticado
                )
                return 200, extrato_fidelidade

            # POST /clientes/{id}/anonimizacao
            if (
                metodo == "POST"
                and caminho.startswith("/clientes/")
                and caminho.endswith("/anonimizacao")
            ):
                perfis_autorizados = ["CLIENTE", "GERENTE", "MATRIZ"]
                usuario_autenticado = ServicoAutenticacao.validar_token(
                    token_jwt, perfis_permitidos=perfis_autorizados
                )
                id_cliente = int(caminho.split("/")[2])
                resultado_anonimizacao = self.app.anonimizar_cliente_lgpd(
                    id_cliente,
                    usuario_autenticado,
                    body.get("motivo", "Solicitação do titular (LGPD)"),
                )
                return 200, resultado_anonimizacao

            # GET /relatorios/vendas
            if metodo == "GET" and caminho == "/relatorios/vendas":
                ServicoAutenticacao.validar_token(
                    token_jwt, perfis_permitidos=["MATRIZ"]
                )
                relatorio_consolidado = (
                    self.app.gerar_relatorio_vendas_matriz(
                        regiao=query.get("regiao")
                    )
                )
                return 200, relatorio_consolidado

            # GET /auditoria/logs
            if metodo == "GET" and caminho == "/auditoria/logs":
                ServicoAutenticacao.validar_token(
                    token_jwt, perfis_permitidos=["MATRIZ", "GERENTE"]
                )
                registros_auditoria = [
                    vars(registro) for registro in self.app.db.logs_auditoria
                ]
                return 200, {
                    "total_registros": len(registros_auditoria),
                    "logs": registros_auditoria,
                }

            return 404, self._formatar_erro_padrao(
                "ENDPOINT_NAO_ENCONTRADO",
                "Endpoint não encontrado.",
                caminho,
            )

        except ErroRegraDeNegocio as erro_negocio:
            return erro_negocio.codigo_http, self._formatar_erro_padrao(
                erro_negocio.codigo_erro,
                erro_negocio.mensagem,
                caminho,
                erro_negocio.detalhes,
            )

    handle_request = processar_requisicao
