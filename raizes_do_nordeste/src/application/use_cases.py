from typing import List, Optional
from src.domain.entities import (
    Cliente,
    ConsentimentoLGPD,
    ErroRegraDeNegocio,
    ItemPedido,
    Pagamento,
    Pedido,
)
from src.infrastructure.repositories_and_services import (
    GatewayPagamento,
    RepositorioBD,
)


class ControladorCasoDeUso:
    """Camada de Aplicação: Orquestra os casos de uso do negócio."""

    def __init__(
        self,
        repositorio_dados: RepositorioBD,
        gateway_pagamento: GatewayPagamento,
    ):
        self.db = repositorio_dados
        self.gateway = gateway_pagamento

    def listar_cardapio_unidade(
        self, id_unidade: int, mes_atual: int = 10
    ) -> List[dict]:
        unidade_selecionada = self.db.unidades.get(id_unidade)
        if not unidade_selecionada:
            raise ErroRegraDeNegocio(
                "Unidade não encontrada.", 404, "UNIDADE_NAO_ENCONTRADA"
            )

        cardapio_disponivel = []
        for (
            id_unidade_estoque,
            id_produto_estoque,
        ), estoque_local in self.db.estoques.items():
            estoque_valido = (
                id_unidade_estoque == id_unidade
                and estoque_local.ativo
                and estoque_local.quantidade > 0
            )
            if estoque_valido:
                produto_catalogo = self.db.produtos[id_produto_estoque]
                try:
                    produto_catalogo.validar_disponibilidade_estrutural(
                        unidade_selecionada, mes_atual
                    )
                    cardapio_disponivel.append(
                        {
                            "id_produto": produto_catalogo.id,
                            "nome": produto_catalogo.nome,
                            "categoria": produto_catalogo.categoria,
                            "preco": estoque_local.preco_local,
                            "estoque_disponivel": estoque_local.quantidade,
                        }
                    )
                except ErroRegraDeNegocio:
                    continue
        return cardapio_disponivel

    def listar_pedidos(
        self,
        canal_pedido: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 10,
    ) -> dict:
        if canal_pedido and canal_pedido not in Pedido.CANAIS_PERMITIDOS:
            raise ErroRegraDeNegocio(
                f"Filtro canalPedido '{canal_pedido}' inválido. Valores aceitos: {Pedido.CANAIS_PERMITIDOS}.",
                400,
                "CANAL_PEDIDO_INVALIDO",
            )
        pedidos_filtrados = []
        for ped in self.db.pedidos.values():
            if canal_pedido and ped.canal != canal_pedido:
                continue
            if status and ped.status != status:
                continue
            pedidos_filtrados.append(
                {
                    "pedidoId": ped.id,
                    "id_pedido": ped.id,
                    "id_unidade": ped.id_unidade,
                    "id_cliente": ped.id_cliente,
                    "canalPedido": ped.canal,
                    "status": ped.status,
                    "valor_total": ped.valor_total,
                    "criado_em": ped.criado_em,
                }
            )
        inicio = max((page - 1) * limit, 0)
        fim = inicio + limit
        return {
            "page": page,
            "limit": limit,
            "total": len(pedidos_filtrados),
            "dados": pedidos_filtrados[inicio:fim],
        }

    def consultar_pedido_por_id(self, id_pedido: int) -> dict:
        ped = self.db.pedidos.get(id_pedido)
        if not ped:
            raise ErroRegraDeNegocio(
                "Pedido não encontrado.", 404, "PEDIDO_NAO_ENCONTRADO"
            )
        return {
            "pedidoId": ped.id,
            "id_pedido": ped.id,
            "id_unidade": ped.id_unidade,
            "id_cliente": ped.id_cliente,
            "canalPedido": ped.canal,
            "status": ped.status,
            "valor_bruto": ped.valor_bruto,
            "valor_desconto": ped.valor_desconto,
            "valor_total": ped.valor_total,
            "itens": [vars(item) for item in ped.itens],
            "criado_em": ped.criado_em,
        }

    def criar_pedido(
        self,
        id_unidade: int,
        canal_atendimento: str,
        itens_solicitados: List[dict],
        id_cliente: Optional[int] = None,
        mes_atual: int = 10,
        hora_atual: int = 14,
    ) -> Pedido:
        unidade_selecionada = self.db.unidades.get(id_unidade)
        if not unidade_selecionada:
            raise ErroRegraDeNegocio(
                "Unidade não encontrada.", 404, "UNIDADE_NAO_ENCONTRADA"
            )

        unidade_selecionada.validar_horario_funcionamento(hora_atual)

        if not canal_atendimento or canal_atendimento not in Pedido.CANAIS_PERMITIDOS:
            raise ErroRegraDeNegocio(
                f"Campo 'canalPedido' obrigatório/inválido ('{canal_atendimento}'). Valores permitidos: {Pedido.CANAIS_PERMITIDOS}.",
                400,
                "CANAL_PEDIDO_INVALIDO",
                [{"field": "canalPedido", "issue": "Informe APP, TOTEM, BALCAO, PICKUP ou WEB"}],
            )
        if not itens_solicitados:
            mensagem_erro = "O pedido deve conter pelo menos um item."
            raise ErroRegraDeNegocio(
                mensagem_erro,
                400,
                "ITENS_OBRIGATORIOS",
                [{"field": "itens", "issue": "Lista de itens vazia"}],
            )

        for idx, item_solicitado in enumerate(itens_solicitados):
            id_produto = item_solicitado.get("id_produto") or item_solicitado.get("produtoId")
            quantidade_solicitada = item_solicitado.get("quantidade", 0)
            if not isinstance(quantidade_solicitada, int) or quantidade_solicitada <= 0:
                mensagem_erro = (
                    "A quantidade do item deve ser um inteiro maior que zero."
                )
                raise ErroRegraDeNegocio(
                    mensagem_erro,
                    400,
                    "QUANTIDADE_INVALIDA",
                    [{"field": f"itens[{idx}].quantidade", "issue": "Deve ser > 0"}],
                )
            produto_catalogo = self.db.produtos.get(id_produto)
            if not produto_catalogo:
                raise ErroRegraDeNegocio(
                    f"Produto {id_produto} inexistente.",
                    404,
                    "PRODUTO_NAO_ENCONTRADO",
                )

            produto_catalogo.validar_disponibilidade_estrutural(
                unidade_selecionada, mes_atual
            )

            estoque_local = self.db.estoques.get((id_unidade, id_produto))
            sem_estoque = (
                not estoque_local
                or not estoque_local.ativo
                or estoque_local.quantidade < quantidade_solicitada
            )
            if sem_estoque:
                saldo_disponivel = (
                    estoque_local.quantidade if estoque_local else 0
                )
                mensagem_erro = (
                    f"Estoque insuficiente para '{produto_catalogo.nome}' "
                    f"na unidade '{unidade_selecionada.nome}' "
                    f"(Disponível: {saldo_disponivel}, "
                    f"Solicitado: {quantidade_solicitada})."
                )
                raise ErroRegraDeNegocio(
                    mensagem_erro,
                    409,
                    "ESTOQUE_INSUFICIENTE",
                    [{"field": f"itens[{idx}].quantidade", "issue": f"Disponível: {saldo_disponivel}"}],
                )

        itens_confirmados: List[ItemPedido] = []
        valor_bruto_pedido = 0.0
        for item_solicitado in itens_solicitados:
            id_produto = item_solicitado.get("id_produto") or item_solicitado.get("produtoId")
            quantidade_solicitada = item_solicitado["quantidade"]
            produto_catalogo = self.db.produtos[id_produto]
            estoque_local = self.db.estoques[(id_unidade, id_produto)]
            estoque_local.reservar(
                quantidade_solicitada, produto_catalogo.nome
            )
            item_pedido = ItemPedido(
                id_produto,
                produto_catalogo.nome,
                quantidade_solicitada,
                estoque_local.preco_local,
            )
            itens_confirmados.append(item_pedido)
            valor_bruto_pedido += item_pedido.subtotal

        valor_bruto_pedido = round(valor_bruto_pedido, 2)
        desconto_fidelidade = 0.0
        if id_cliente:
            cliente_cadastrado = self.db.clientes.get(id_cliente)
            if cliente_cadastrado:
                desconto_fidelidade = (
                    cliente_cadastrado.calcular_desconto_progressivo(
                        valor_bruto_pedido
                    )
                )

        novo_pedido = Pedido(
            id=self.db._sequencia_pedido,
            id_unidade=id_unidade,
            canal=canal_atendimento,
            itens=itens_confirmados,
            id_cliente=id_cliente,
            status="AGUARDANDO_PAGAMENTO",
            valor_bruto=valor_bruto_pedido,
            valor_desconto=desconto_fidelidade,
            valor_total=round(valor_bruto_pedido - desconto_fidelidade, 2),
        )
        self.db._sequencia_pedido += 1
        self.db.pedidos[novo_pedido.id] = novo_pedido
        self.db.salvar_pedido_sqlite(novo_pedido)
        return novo_pedido

    def solicitar_pagamento(
        self, id_pedido: int, chave_idempotencia: str, dados_pagamento: dict
    ) -> dict:
        if chave_idempotencia in self.db.pagamentos_por_idempotencia:
            pagamento_existente = self.db.pagamentos_por_idempotencia[
                chave_idempotencia
            ]
            pedido_associado = self.db.pedidos[pagamento_existente.id_pedido]
            if pagamento_existente.status == "APROVADO":
                resultado_gateway = "SUCCESS"
            elif pagamento_existente.status == "RECUSADO":
                resultado_gateway = "FAILURE"
            else:
                resultado_gateway = "PENDING"
            return {
                "id_pagamento": pagamento_existente.id,
                "status": pagamento_existente.status,
                "resultado_gateway": resultado_gateway,
                "id_transacao_externa": (
                    pagamento_existente.id_transacao_externa
                ),
                "status_pedido": pedido_associado.status,
                "idempotente": True,
            }

        pedido_encontrado = self.db.pedidos.get(id_pedido)
        if not pedido_encontrado:
            raise ErroRegraDeNegocio(
                "Pedido não encontrado.", 404, "PEDIDO_NAO_ENCONTRADO"
            )

        resposta_gateway = self.gateway.processar_pagamento_simulado(
            chave_idempotencia,
            pedido_encontrado.valor_total,
            dados_pagamento,
        )
        novo_pagamento = Pagamento(
            id=self.db._sequencia_pagamento,
            id_pedido=pedido_encontrado.id,
            chave_idempotencia=chave_idempotencia,
            valor=pedido_encontrado.valor_total,
            status=resposta_gateway["status"],
            id_transacao_externa=resposta_gateway["id_transacao_externa"],
        )
        self.db._sequencia_pagamento += 1
        self.db.pagamentos[novo_pagamento.id] = novo_pagamento
        self.db.pagamentos_por_idempotencia[chave_idempotencia] = (
            novo_pagamento
        )

        pontos_creditados = 0
        if (
            novo_pagamento.status == "APROVADO"
            and pedido_encontrado.status == "AGUARDANDO_PAGAMENTO"
        ):
            pedido_encontrado.avancar_status(
                "CONFIRMADO", status_pagamento="APROVADO"
            )
            self.db.salvar_pedido_sqlite(pedido_encontrado)
            if pedido_encontrado.id_cliente:
                cliente_fidelidade = self.db.clientes.get(
                    pedido_encontrado.id_cliente
                )
                elegivel_pontos = (
                    cliente_fidelidade
                    and cliente_fidelidade.consentimento_lgpd
                    and not cliente_fidelidade.anonimizado
                )
                if elegivel_pontos:
                    pontos_creditados = cliente_fidelidade.creditar_pontos(
                        pedido_encontrado.valor_total
                    )

        return {
            "id_pagamento": novo_pagamento.id,
            "status": novo_pagamento.status,
            "resultado_gateway": resposta_gateway["resultado_gateway"],
            "id_transacao_externa": novo_pagamento.id_transacao_externa,
            "status_pedido": pedido_encontrado.status,
            "pontos_creditados": pontos_creditados,
            "mensagem": resposta_gateway["mensagem"],
        }

    def processar_webhook_pagamento(
        self,
        id_pagamento: int,
        id_transacao_externa: str,
        resultado_transacao: str,
    ) -> dict:
        chave_webhook = f"{id_transacao_externa}:{resultado_transacao}"
        if chave_webhook in self.db.webhooks_processados:
            return {
                "status": "IGNORADO_IDEMPOTENTE",
                "id_pagamento": id_pagamento,
            }

        pagamento_registrado = self.db.pagamentos.get(id_pagamento)
        if not pagamento_registrado:
            raise ErroRegraDeNegocio(
                "Registro de pagamento não encontrado.",
                404,
                "PAGAMENTO_NAO_ENCONTRADO",
            )

        pedido_associado = self.db.pedidos[pagamento_registrado.id_pedido]
        self.db.webhooks_processados.add(chave_webhook)

        if resultado_transacao in ("APROVADO", "SUCCESS"):
            pagamento_registrado.status = "APROVADO"
            pontos_creditados = 0
            if pedido_associado.status == "AGUARDANDO_PAGAMENTO":
                pedido_associado.avancar_status(
                    "CONFIRMADO", status_pagamento="APROVADO"
                )
                self.db.salvar_pedido_sqlite(pedido_associado)
                if pedido_associado.id_cliente:
                    cliente_fidelidade = self.db.clientes.get(
                        pedido_associado.id_cliente
                    )
                    elegivel_pontos = (
                        cliente_fidelidade
                        and cliente_fidelidade.consentimento_lgpd
                        and not cliente_fidelidade.anonimizado
                    )
                    if elegivel_pontos:
                        pontos_creditados = (
                            cliente_fidelidade.creditar_pontos(
                                pedido_associado.valor_total
                            )
                        )
            return {
                "status_pedido": pedido_associado.status,
                "status_pagamento": pagamento_registrado.status,
                "resultado_gateway": "SUCCESS",
                "pontos_creditados": pontos_creditados,
            }

        pagamento_registrado.status = "RECUSADO"
        return {
            "status_pedido": pedido_associado.status,
            "status_pagamento": pagamento_registrado.status,
            "resultado_gateway": "FAILURE",
            "pontos_creditados": 0,
        }

    def atualizar_status_pedido(
        self,
        id_pedido: int,
        novo_status: str,
        usuario_autenticado: Optional[dict] = None,
    ) -> Pedido:
        pedido_encontrado = self.db.pedidos.get(id_pedido)
        if not pedido_encontrado:
            raise ErroRegraDeNegocio(
                "Pedido não encontrado.", 404, "PEDIDO_NAO_ENCONTRADO"
            )

        pagamentos_do_pedido = [
            pagamento
            for pagamento in self.db.pagamentos.values()
            if pagamento.id_pedido == id_pedido
        ]
        pagamento_aprovado = any(
            pagamento.status == "APROVADO"
            for pagamento in pagamentos_do_pedido
        )
        status_pagamento = "APROVADO" if pagamento_aprovado else "PENDENTE"
        status_anterior = pedido_encontrado.status
        pedido_encontrado.avancar_status(
            novo_status, status_pagamento=status_pagamento
        )
        self.db.salvar_pedido_sqlite(pedido_encontrado)
        if usuario_autenticado:
            self.db.registrar_auditoria(
                id_usuario=usuario_autenticado["usuario_id"],
                perfil_usuario=usuario_autenticado["perfil"],
                tipo_operacao="MUDANCA_STATUS_PEDIDO",
                entidade_afetada=f"Pedido:{pedido_encontrado.id}",
                motivo_operacao=f"Transição operacional para {novo_status}",
                valor_anterior=status_anterior,
                valor_novo=pedido_encontrado.status,
            )
        return pedido_encontrado

    def cancelar_pedido_auditado(
        self, id_pedido: int, usuario_autenticado: dict, motivo: str
    ) -> Pedido:
        if not motivo or len(motivo.strip()) < 5:
            mensagem_erro = (
                "Motivo detalhado é obrigatório para cancelar um pedido "
                "(Regra R5)."
            )
            raise ErroRegraDeNegocio(
                mensagem_erro,
                400,
                "MOTIVO_CANCELAMENTO_OBRIGATORIO",
                [{"field": "motivo", "issue": "Mínimo de 5 caracteres"}],
            )

        pedido_encontrado = self.db.pedidos.get(id_pedido)
        if not pedido_encontrado:
            raise ErroRegraDeNegocio(
                "Pedido não encontrado.", 404, "PEDIDO_NAO_ENCONTRADO"
            )

        status_anterior = pedido_encontrado.status
        pedido_encontrado.avancar_status("CANCELADO")
        self.db.salvar_pedido_sqlite(pedido_encontrado)
        for item_pedido in pedido_encontrado.itens:
            estoque_local = self.db.estoques.get(
                (pedido_encontrado.id_unidade, item_pedido.id_produto)
            )
            if estoque_local:
                estoque_local.quantidade += item_pedido.quantidade

        self.db.registrar_auditoria(
            id_usuario=usuario_autenticado["usuario_id"],
            perfil_usuario=usuario_autenticado["perfil"],
            tipo_operacao="CANCELAMENTO_PEDIDO",
            entidade_afetada=f"Pedido:{pedido_encontrado.id}",
            motivo_operacao=motivo.strip(),
            valor_anterior=status_anterior,
            valor_novo=pedido_encontrado.status,
        )
        return pedido_encontrado

    def movimentar_estoque_unidade(
        self,
        id_unidade: int,
        id_produto: int,
        quantidade_ajuste: int,
        usuario_autenticado: dict,
        motivo: str = "Ajuste operacional de inventário",
    ) -> dict:
        estoque_local = self.db.estoques.get((id_unidade, id_produto))
        if not estoque_local:
            raise ErroRegraDeNegocio(
                "Estoque local não encontrado para a unidade/produto.",
                404,
                "ESTOQUE_NAO_ENCONTRADO",
            )
        saldo_anterior = estoque_local.quantidade
        novo_saldo = saldo_anterior + quantidade_ajuste
        if novo_saldo < 0:
            raise ErroRegraDeNegocio(
                "A movimentação de saída não pode deixar o estoque negativo.",
                422,
                "SALDO_ESTOQUE_NEGATIVO",
            )
        estoque_local.quantidade = novo_saldo
        self.db.registrar_auditoria(
            id_usuario=usuario_autenticado["usuario_id"],
            perfil_usuario=usuario_autenticado["perfil"],
            tipo_operacao="AJUSTE_ESTOQUE",
            entidade_afetada=f"EstoqueUnidade:{id_unidade}:{id_produto}",
            motivo_operacao=motivo,
            valor_anterior=str(saldo_anterior),
            valor_novo=str(novo_saldo),
        )
        return {
            "id_unidade": id_unidade,
            "id_produto": id_produto,
            "saldo_anterior": saldo_anterior,
            "saldo_atual": novo_saldo,
        }

    def registrar_consentimento_lgpd(
        self,
        id_cliente: int,
        consentimento_aceito: bool,
        versao_termo: str = "v1.0-2026",
    ) -> Cliente:
        if not consentimento_aceito:
            mensagem_erro = (
                "O consentimento explícito (opt-in = True) é obrigatório "
                "para aderir ao programa de fidelização."
            )
            raise ErroRegraDeNegocio(
                mensagem_erro, 422, "CONSENTIMENTO_EXPLICITO_OBRIGATORIO"
            )
        cliente_cadastrado = self.db.clientes.get(id_cliente)
        if not cliente_cadastrado:
            raise ErroRegraDeNegocio(
                "Cliente não encontrado.", 404, "CLIENTE_NAO_ENCONTRADO"
            )
        cliente_cadastrado.consentimento_lgpd = True
        self.db.consentimentos.append(
            ConsentimentoLGPD(
                id_cliente, "FIDELIDADE_E_MARKETING", True, versao_termo
            )
        )
        return cliente_cadastrado

    def consultar_perfil_fidelidade(
        self, id_cliente: int, usuario_autenticado: dict
    ) -> dict:
        cliente_cadastrado = self.db.clientes.get(id_cliente)
        if not cliente_cadastrado:
            raise ErroRegraDeNegocio(
                "Cliente não encontrado.", 404, "CLIENTE_NAO_ENCONTRADO"
            )
        self.db.registrar_auditoria(
            id_usuario=usuario_autenticado["usuario_id"],
            perfil_usuario=usuario_autenticado["perfil"],
            tipo_operacao="ACESSO_DADOS_LGPD",
            entidade_afetada=f"Cliente:{cliente_cadastrado.id}",
            motivo_operacao="Consulta de perfil e extrato de fidelização",
            valor_anterior="-",
            valor_novo="Leitura autorizada",
        )
        cpf_mascarado = (
            "***.***.***-**"
            if cliente_cadastrado.anonimizado
            else f"***.{cliente_cadastrado.cpf[4:11]}-**"
        )
        return {
            "id": cliente_cadastrado.id,
            "nome": cliente_cadastrado.nome,
            "cpf": cpf_mascarado,
            "saldo_pontos": cliente_cadastrado.saldo_pontos,
            "consentimento_lgpd": cliente_cadastrado.consentimento_lgpd,
            "anonimizado": cliente_cadastrado.anonimizado,
        }

    def anonimizar_cliente_lgpd(
        self,
        id_cliente: int,
        usuario_autenticado: dict,
        motivo: str = "Solicitação do titular (Art. 18 LGPD)",
    ) -> dict:
        cliente_cadastrado = self.db.clientes.get(id_cliente)
        if not cliente_cadastrado:
            raise ErroRegraDeNegocio(
                "Cliente não encontrado.", 404, "CLIENTE_NAO_ENCONTRADO"
            )
        nome_anterior = cliente_cadastrado.nome
        cliente_cadastrado.anonimizar()
        self.db.registrar_auditoria(
            id_usuario=usuario_autenticado["usuario_id"],
            perfil_usuario=usuario_autenticado["perfil"],
            tipo_operacao="ANONIMIZACAO_LGPD",
            entidade_afetada=f"Cliente:{cliente_cadastrado.id}",
            motivo_operacao=motivo,
            valor_anterior=nome_anterior,
            valor_novo=cliente_cadastrado.nome,
        )
        return {
            "id": cliente_cadastrado.id,
            "nome": cliente_cadastrado.nome,
            "anonimizado": cliente_cadastrado.anonimizado,
        }

    def gerar_relatorio_vendas_matriz(
        self, regiao: Optional[str] = None
    ) -> dict:
        vendas_por_unidade = {}
        vendas_por_canal = {}
        contagem_produtos = {}
        faturamento_total = 0.0

        estados_contabilizados = (
            "CONFIRMADO",
            "EM_PREPARO",
            "PRONTO",
            "ENTREGUE",
        )
        for pedido_registrado in self.db.pedidos.values():
            if pedido_registrado.status in estados_contabilizados:
                unidade_venda = self.db.unidades[pedido_registrado.id_unidade]
                if regiao and unidade_venda.regiao != regiao:
                    continue
                total_unidade = vendas_por_unidade.get(
                    unidade_venda.nome, 0.0
                )
                vendas_por_unidade[unidade_venda.nome] = round(
                    total_unidade + pedido_registrado.valor_total, 2
                )
                total_canal = vendas_por_canal.get(
                    pedido_registrado.canal, 0.0
                )
                vendas_por_canal[pedido_registrado.canal] = round(
                    total_canal + pedido_registrado.valor_total, 2
                )
                faturamento_total = round(
                    faturamento_total + pedido_registrado.valor_total, 2
                )
                for item_pedido in pedido_registrado.itens:
                    quantidade_acumulada = contagem_produtos.get(
                        item_pedido.nome_produto, 0
                    )
                    contagem_produtos[item_pedido.nome_produto] = (
                        quantidade_acumulada + item_pedido.quantidade
                    )

        produtos_ordenados = sorted(
            contagem_produtos.items(), key=lambda item: item[1], reverse=True
        )
        return {
            "faturamento_total": faturamento_total,
            "vendas_por_unidade": vendas_por_unidade,
            "vendas_por_canal": vendas_por_canal,
            "produtos_mais_consumidos": [
                {"produto": nome_produto, "quantidade": total_vendido}
                for nome_produto, total_vendido in produtos_ordenados
            ],
        }
