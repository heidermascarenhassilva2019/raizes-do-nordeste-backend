import unittest
from src.api.controller import ControladorAPI
from src.application.use_cases import ControladorCasoDeUso
from src.infrastructure.repositories_and_services import (
    GatewayPagamento,
    RepositorioBD,
    ServicoAutenticacao,
)


class TestRaizesDoNordestePlanoDeTestes(unittest.TestCase):
    def setUp(self):
        self.repositorio_dados = RepositorioBD()
        self.gateway_pagamento = GatewayPagamento()
        self.servico_aplicacao = ControladorCasoDeUso(
            self.repositorio_dados, self.gateway_pagamento
        )
        self.controlador_api = ControladorAPI(
            self.servico_aplicacao
        )

        jwt_cliente1 = ServicoAutenticacao.gerar_token("cliente1", "CLIENTE")
        jwt_funcionario1 = ServicoAutenticacao.gerar_token(
            "funcionario1", "ATENDENTE", 1
        )
        jwt_funcionario2 = ServicoAutenticacao.gerar_token(
            "funcionario2", "COZINHEIRO", 1
        )
        jwt_funcionario3 = ServicoAutenticacao.gerar_token(
            "funcionario3", "GERENTE", 1
        )
        jwt_colaborador1 = ServicoAutenticacao.gerar_token(
            "colaborador1", "MATRIZ"
        )

        self.token_cliente1 = f"Bearer {jwt_cliente1}"
        self.token_funcionario1 = f"Bearer {jwt_funcionario1}"
        self.token_funcionario2 = f"Bearer {jwt_funcionario2}"
        self.token_funcionario3 = f"Bearer {jwt_funcionario3}"
        self.token_colaborador1 = f"Bearer {jwt_colaborador1}"

    def test_T01_login_valido_retorna_200_e_token(self):
        # T01 [Positivo]: Login com credenciais válidas | Saída: 200 OK + accessToken
        status_sucesso, resposta_login = (
            self.controlador_api.processar_requisicao(
                "POST",
                "/auth/login",
                body={
                    "email": "cliente1@raizes.com",
                    "senha": "123",
                },
            )
        )
        self.assertEqual(status_sucesso, 200)
        self.assertEqual(resposta_login["perfil"], "CLIENTE")
        self.assertEqual(resposta_login["usuarioId"], "cliente1")
        self.assertIn("accessToken", resposta_login)

    def test_T02_acesso_sem_token_retorna_401(self):
        # T02 [Negativo]: Acesso sem token em rota protegida | Saída: 401 + erro padrão
        status_erro, corpo_erro = self.controlador_api.processar_requisicao(
            "GET",
            "/pedidos",
            headers={},
        )
        self.assertEqual(status_erro, 401)
        self.assertEqual(corpo_erro["error"], "TOKEN_AUSENTE_OU_INVALIDO")
        self.assertIn("timestamp", corpo_erro)
        self.assertEqual(corpo_erro["path"], "/pedidos")

    def test_T03_acesso_perfil_sem_permissao_retorna_403(self):
        # T03 [Negativo]: Perfil sem permissão (GERENTE em rota da MATRIZ) | Saída: 403
        status_negado, corpo_erro = self.controlador_api.processar_requisicao(
            "GET",
            "/relatorios/vendas",
            headers={"Authorization": self.token_funcionario3},
        )
        self.assertEqual(status_negado, 403)
        self.assertEqual(corpo_erro["error"], "PERMISSAO_NEGADA")

    def test_T04_validacao_campo_obrigatorio_ausente_retorna_400(self):
        # T04 [Negativo]: Campo obrigatório ausente (sem canalPedido ou itens) | Saída: 400
        status_invalido, corpo_erro = self.controlador_api.processar_requisicao(
            "POST",
            "/pedidos",
            headers={"Authorization": self.token_cliente1},
            body={"id_unidade": 1, "canalPedido": "APP", "itens": []},
        )
        self.assertEqual(status_invalido, 400)
        self.assertEqual(corpo_erro["error"], "ITENS_OBRIGATORIOS")
        self.assertTrue(len(corpo_erro["details"]) > 0)

    def test_T05_validacao_formato_ou_quantidade_invalida_retorna_400(self):
        # T05 [Negativo]: Quantidade negativa e e-mail malformado | Saída: 400
        status_qtd, corpo_qtd = self.controlador_api.processar_requisicao(
            "POST",
            "/pedidos",
            headers={"Authorization": self.token_cliente1},
            body={
                "id_unidade": 1,
                "canalPedido": "WEB",
                "itens": [{"id_produto": 1, "quantidade": -2}],
            },
        )
        self.assertEqual(status_qtd, 400)
        self.assertEqual(corpo_qtd["error"], "QUANTIDADE_INVALIDA")

        status_email, _ = self.controlador_api.processar_requisicao(
            "POST",
            "/auth/login",
            body={"email": "email_invalido_sem_arroba", "senha": "123"},
        )
        self.assertEqual(status_email, 400)

    def test_T06_criar_pedido_valido_e_filtrar_por_canal(self):
        # T06 [Positivo]: Criar pedido válido e consultar por ?canalPedido=TOTEM | Saída: 201 e 200
        status_criado, resposta_pedido = (
            self.controlador_api.processar_requisicao(
                "POST",
                "/pedidos",
                headers={"Authorization": self.token_cliente1},
                body={
                    "id_unidade": 1,
                    "canalPedido": "TOTEM",
                    "id_cliente": 1,
                    "itens": [{"id_produto": 1, "quantidade": 2}],
                },
            )
        )
        self.assertEqual(status_criado, 201)
        self.assertEqual(resposta_pedido["canalPedido"], "TOTEM")

        status_filtro, lista = self.controlador_api.processar_requisicao(
            "GET",
            "/pedidos",
            headers={"Authorization": self.token_cliente1},
            query={"canalPedido": "TOTEM", "page": "1", "limit": "10"},
        )
        self.assertEqual(status_filtro, 200)
        self.assertEqual(lista["total"], 1)
        self.assertEqual(lista["dados"][0]["canalPedido"], "TOTEM")

    def test_T07_pedido_unidade_ou_produto_inexistente_retorna_404(self):
        # T07 [Negativo]: Pedido com unidade ou produto inexistente | Saída: 404 Not Found
        status_unid, err_unid = self.controlador_api.processar_requisicao(
            "POST",
            "/pedidos",
            headers={"Authorization": self.token_cliente1},
            body={
                "id_unidade": 999,
                "canalPedido": "APP",
                "itens": [{"id_produto": 1, "quantidade": 1}],
            },
        )
        self.assertEqual(status_unid, 404)
        self.assertEqual(err_unid["error"], "UNIDADE_NAO_ENCONTRADA")

        status_prod, err_prod = self.controlador_api.processar_requisicao(
            "POST",
            "/pedidos",
            headers={"Authorization": self.token_cliente1},
            body={
                "id_unidade": 1,
                "canalPedido": "APP",
                "itens": [{"id_produto": 999, "quantidade": 1}],
            },
        )
        self.assertEqual(status_prod, 404)
        self.assertEqual(err_prod["error"], "PRODUTO_NAO_ENCONTRADO")

    def test_T08_pedido_sem_estoque_retorna_409_conflict(self):
        # T08 [Negativo]: Pedido com estoque insuficiente | Saída Esperada: 409 Conflict
        status_conflito, resposta_erro = (
            self.controlador_api.processar_requisicao(
                "POST",
                "/pedidos",
                headers={"Authorization": self.token_cliente1},
                body={
                    "id_unidade": 1,
                    "canalPedido": "APP",
                    "itens": [{"id_produto": 1, "quantidade": 999}],
                },
            )
        )
        self.assertEqual(status_conflito, 409)
        self.assertEqual(resposta_erro["error"], "ESTOQUE_INSUFICIENTE")
        self.assertIn("Estoque insuficiente", resposta_erro["message"])

    def test_T09_pagamento_mock_aprovado_e_atualizacao_status_cozinha(self):
        # T09 [Positivo]: Pagamento mock aprovado -> status CONFIRMADO -> EM_PREPARO -> PRONTO -> ENTREGUE
        _, ped = self.controlador_api.processar_requisicao(
            "POST",
            "/pedidos",
            headers={"Authorization": self.token_cliente1},
            body={
                "id_unidade": 1,
                "canalPedido": "APP",
                "id_cliente": 1,
                "itens": [{"id_produto": 1, "quantidade": 2}],
            },
        )
        id_ped = ped["pedidoId"]

        status_aprov, res_aprov = self.controlador_api.processar_requisicao(
            "POST",
            f"/pedidos/{id_ped}/pagamentos",
            headers={"Idempotency-Key": "chave-pag-001"},
            body={
                "dados_pagamento": {
                    "token_pagamento": "tok_pagamento_aprovado",
                    "simularResultado": "SUCCESS",
                }
            },
        )
        self.assertEqual(status_aprov, 200)
        self.assertEqual(res_aprov["status"], "APROVADO")
        self.assertEqual(res_aprov["status_pedido"], "CONFIRMADO")
        self.assertGreater(res_aprov["pontos_creditados"], 0)

        for prox_status in ("EM_PREPARO", "PRONTO", "ENTREGUE"):
            st_code, res_st = self.controlador_api.processar_requisicao(
                "PATCH",
                f"/pedidos/{id_ped}/status",
                headers={"Authorization": self.token_funcionario2},
                body={"novo_status": prox_status},
            )
            self.assertEqual(st_code, 200)
            self.assertEqual(res_st["status"], prox_status)

    def test_T10_pagamento_mock_recusado_e_bloqueio_preparo(self):
        # T10 [Negativo]: Pagamento mock recusado mantém AGUARDANDO_PAGAMENTO e bloqueia preparo (409)
        _, ped = self.controlador_api.processar_requisicao(
            "POST",
            "/pedidos",
            body={
                "id_unidade": 1,
                "canalPedido": "TOTEM",
                "itens": [{"id_produto": 2, "quantidade": 1}],
            },
        )
        id_ped = ped["pedidoId"]

        st_rec, res_rec = self.controlador_api.processar_requisicao(
            "POST",
            f"/pedidos/{id_ped}/pagamentos",
            headers={"Idempotency-Key": "chave-pag-002"},
            body={
                "dados_pagamento": {
                    "token_pagamento": "tok_cartao_recusado",
                    "simularResultado": "FAILURE",
                }
            },
        )
        self.assertEqual(st_rec, 200)
        self.assertEqual(res_rec["status"], "RECUSADO")
        self.assertEqual(res_rec["status_pedido"], "AGUARDANDO_PAGAMENTO")

        st_bloq, _ = self.controlador_api.processar_requisicao(
            "PATCH",
            f"/pedidos/{id_ped}/status",
            headers={"Authorization": self.token_funcionario2},
            body={"novo_status": "EM_PREPARO"},
        )
        self.assertEqual(st_bloq, 409)

    def test_T11_logs_auditoria_cancelamento_e_lgpd_anonimizacao(self):
        # T11 [Positivo]: Cancelamento por gerente, anonimização LGPD e consulta de logs de auditoria
        _, ped = self.controlador_api.processar_requisicao(
            "POST",
            "/pedidos",
            body={
                "id_unidade": 1,
                "canalPedido": "BALCAO",
                "itens": [{"id_produto": 1, "quantidade": 1}],
            },
        )
        id_ped = ped["pedidoId"]

        st_canc, _ = self.controlador_api.processar_requisicao(
            "POST",
            f"/pedidos/{id_ped}/cancelamento",
            headers={"Authorization": self.token_funcionario3},
            body={"motivo": "Cancelamento autorizado por funcionario3"},
        )
        self.assertEqual(st_canc, 200)

        st_anon, dados_anon = self.controlador_api.processar_requisicao(
            "POST",
            "/clientes/1/anonimizacao",
            headers={"Authorization": self.token_cliente1},
            body={"motivo": "Direito de exclusão/anonimização LGPD"},
        )
        self.assertEqual(st_anon, 200)
        self.assertTrue(dados_anon["anonimizado"])
        self.assertTrue(dados_anon["nome"].startswith("CLIENTE_ANONIMIZADO_"))

        st_logs, res_logs = self.controlador_api.processar_requisicao(
            "GET",
            "/auditoria/logs",
            headers={"Authorization": self.token_colaborador1},
        )
        self.assertEqual(st_logs, 200)
        self.assertGreaterEqual(res_logs["total_registros"], 2)

    def test_T12_consulta_cardapio_fidelidade_e_relatorio_matriz(self):
        # T12 [Positivo]: Consulta cardápio junino, extrato fidelidade (CPF mascarado) e relatório Matriz
        st_card, res_card = self.controlador_api.processar_requisicao(
            "GET", "/unidades/1/cardapio", query={"mes": "6"}
        )
        self.assertEqual(st_card, 200)
        self.assertEqual(len(res_card["dados"]), 4)

        st_fid, res_fid = self.controlador_api.processar_requisicao(
            "GET",
            "/clientes/1/fidelidade",
            headers={"Authorization": self.token_cliente1},
        )
        self.assertEqual(st_fid, 200)
        self.assertTrue(res_fid["cpf"].startswith("***."))

        st_rel, res_rel = self.controlador_api.processar_requisicao(
            "GET",
            "/relatorios/vendas",
            headers={"Authorization": self.token_colaborador1},
        )
        self.assertEqual(st_rel, 200)
        self.assertIn("vendas_por_canal", res_rel)


if __name__ == "__main__":
    unittest.main()
