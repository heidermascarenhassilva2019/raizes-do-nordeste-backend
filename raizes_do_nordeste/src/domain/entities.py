import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


def _agora_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ErroRegraDeNegocio(Exception):
    def __init__(
        self,
        mensagem: str,
        codigo_http: int = 422,
        codigo_erro: str = "REGRA_DE_NEGOCIO_VIOLADA",
        detalhes: Optional[List[dict]] = None,
    ):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo_http = codigo_http
        self.codigo_erro = codigo_erro
        self.detalhes = detalhes or []


class PermissaoNegada(ErroRegraDeNegocio):
    def __init__(
        self,
        mensagem: str = "Acesso negado para o perfil do usuário atual.",
        codigo_http: int = 403,
        codigo_erro: Optional[str] = None,
    ):
        if not codigo_erro:
            codigo_erro = (
                "NAO_AUTENTICADO" if codigo_http == 401 else "ACESSO_NEGADO"
            )
        super().__init__(
            mensagem, codigo_http=codigo_http, codigo_erro=codigo_erro
        )


@dataclass
class Unidade:
    id: int
    nome: str
    cidade: str
    regiao: str
    tipo_cozinha: str  # "COMPLETA" ou "REDUZIDA"
    hora_abertura: int = 6
    hora_fechamento: int = 22
    ativa: bool = True

    def validar_horario_funcionamento(self, hora_atual: int):
        # Valida se a unidade está ativa e dentro do horário de funcionamento
        horario_valido = self.hora_abertura <= hora_atual < self.hora_fechamento
        if not self.ativa or not horario_valido:
            mensagem_erro = (
                f"Unidade '{self.nome}' fechada neste horário. "
                f"Funcionamento: {self.hora_abertura}h às "
                f"{self.hora_fechamento}h."
            )
            raise ErroRegraDeNegocio(
                mensagem_erro, 422, "UNIDADE_FECHADA"
            )


@dataclass
class Produto:
    id: int
    nome: str
    categoria: str
    preco_base: float
    exige_cozinha_completa: bool = False
    sazonal: bool = False
    meses_sazonais: List[int] = field(default_factory=list)
    regiao_especifica: Optional[str] = None

    def validar_disponibilidade_estrutural(
        self, unidade: Unidade, mes_atual: int
    ):
        # Impede que unidades de cozinha reduzida vendam pratos de cozinha completa
        if self.exige_cozinha_completa and unidade.tipo_cozinha == "REDUZIDA":
            mensagem_erro = (
                f"O produto '{self.nome}' exige cozinha completa e não é "
                f"compatível com a unidade '{unidade.nome}'."
            )
            raise ErroRegraDeNegocio(
                mensagem_erro, 422, "COZINHA_INCOMPATIVEL"
            )
        # Verifica disponibilidade de itens sazonais e regionais
        if self.sazonal and mes_atual not in self.meses_sazonais:
            mensagem_erro = (
                f"O produto '{self.nome}' é sazonal (cardápio junino) e não "
                f"está disponível no mês consultado ({mes_atual})."
            )
            raise ErroRegraDeNegocio(
                mensagem_erro, 422, "PRODUTO_FORA_DE_EPOCA"
            )
        if self.regiao_especifica and self.regiao_especifica != unidade.regiao:
            mensagem_erro = (
                f"O produto '{self.nome}' é exclusivo da região "
                f"{self.regiao_especifica}."
            )
            raise ErroRegraDeNegocio(
                mensagem_erro, 422, "PRODUTO_RESTRITO_REGIAO"
            )


@dataclass
class EstoqueUnidade:
    id_unidade: int
    id_produto: int
    quantidade: int
    preco_local: float
    ativo: bool = True

    def reservar(self, quantidade_solicitada: int, nome_produto: str):
        # Verifica disponibilidade e deduz a quantidade no estoque local da unidade
        if not self.ativo or self.quantidade < quantidade_solicitada:
            mensagem_erro = (
                f"Estoque insuficiente para '{nome_produto}' nesta unidade "
                f"(Disponível: {self.quantidade}, "
                f"Solicitado: {quantidade_solicitada})."
            )
            raise ErroRegraDeNegocio(
                mensagem_erro,
                409,
                "ESTOQUE_INSUFICIENTE",
                [{"field": "quantidade", "issue": f"Disponível: {self.quantidade}"}],
            )
        self.quantidade -= quantidade_solicitada


@dataclass
class ConsentimentoLGPD:
    id_cliente: int
    finalidade: str
    aceito: bool
    versao_termo: str
    data_hora: str = field(default_factory=_agora_utc_iso)
    data_revogacao: Optional[str] = None


@dataclass
class Cliente:
    id: int
    nome: str
    cpf: str
    idade: int
    contato: str
    consentimento_lgpd: bool = False
    saldo_pontos: int = 0
    frequencia_consumo: int = 0
    anonimizado: bool = False

    def validar_consentimento_fidelidade(self):
        # Exige consentimento explícito ativo (LGPD) para operações de fidelidade
        if self.anonimizado or not self.consentimento_lgpd:
            mensagem_erro = (
                "Operação de fidelização bloqueada: cliente sem "
                "consentimento explícito LGPD ativo."
            )
            raise ErroRegraDeNegocio(
                mensagem_erro, 422, "CONSENTIMENTO_LGPD_OBRIGATORIO"
            )

    def creditar_pontos(self, valor_pago: float):
        # Converte o valor pago em pontos de fidelidade para clientes ativos
        self.validar_consentimento_fidelidade()
        pontos_acumulados = int(valor_pago)
        self.saldo_pontos += pontos_acumulados
        self.frequencia_consumo += 1
        return pontos_acumulados

    def calcular_desconto_progressivo(self, valor_bruto: float) -> float:
        if not self.consentimento_lgpd or self.anonimizado:
            return 0.0
        if self.saldo_pontos >= 200:
            return round(valor_bruto * 0.15, 2)
        elif self.saldo_pontos >= 100:
            return round(valor_bruto * 0.10, 2)
        elif self.saldo_pontos >= 50:
            return round(valor_bruto * 0.05, 2)
        return 0.0

    def anonimizar(self):
        # Anonimiza dados pessoais (LGPD) mantendo o ID para histórico de vendas
        chave_identificacao = f"{self.id}-{self.cpf}".encode()
        codigo_anonimo = hashlib.sha256(chave_identificacao).hexdigest()[:10]
        self.nome = f"CLIENTE_ANONIMIZADO_{codigo_anonimo}"
        self.cpf = "***.***.***-**"
        self.contato = f"anonimizado.{codigo_anonimo}@anonimo.local"
        self.consentimento_lgpd = False
        self.saldo_pontos = 0
        self.anonimizado = True


@dataclass
class ItemPedido:
    id_produto: int
    nome_produto: str
    quantidade: int
    preco_unitario: float

    @property
    def subtotal(self) -> float:
        return round(self.quantidade * self.preco_unitario, 2)


@dataclass
class Pedido:
    id: int
    id_unidade: int
    canal: str  # "APP", "TOTEM", "BALCAO", "PICKUP", "WEB"
    itens: List[ItemPedido]
    id_cliente: Optional[int] = None
    status: str = "AGUARDANDO_PAGAMENTO"
    valor_bruto: float = 0.0
    valor_desconto: float = 0.0
    valor_total: float = 0.0
    criado_em: str = field(default_factory=_agora_utc_iso)

    CANAIS_PERMITIDOS = ("APP", "TOTEM", "BALCAO", "PICKUP", "WEB")

    TRANSICOES_VALIDAS = {
        "AGUARDANDO_PAGAMENTO": ["CONFIRMADO", "CANCELADO"],
        "CONFIRMADO": ["EM_PREPARO", "CANCELADO"],
        "EM_PREPARO": ["PRONTO", "CANCELADO"],
        "PRONTO": ["ENTREGUE"],
        "ENTREGUE": [],
        "CANCELADO": [],
    }

    def avancar_status(
        self, novo_status: str, status_pagamento: Optional[str] = None
    ):
        # Bloqueia envio para preparo na cozinha sem pagamento aprovado
        if novo_status == "EM_PREPARO" and status_pagamento != "APROVADO":
            mensagem_erro = (
                "O pedido não pode avançar para 'EM_PREPARO' sem "
                "pagamento confirmado ('APROVADO')."
            )
            raise ErroRegraDeNegocio(
                mensagem_erro, 409, "PAGAMENTO_NAO_CONFIRMADO"
            )
        if novo_status not in self.TRANSICOES_VALIDAS.get(self.status, []):
            mensagem_erro = (
                f"Transição de estado inválida: {self.status} -> {novo_status}."
            )
            raise ErroRegraDeNegocio(
                mensagem_erro, 409, "TRANSICAO_STATUS_INVALIDA"
            )
        self.status = novo_status


@dataclass
class Pagamento:
    id: int
    id_pedido: int
    chave_idempotencia: str
    valor: float
    gateway: str = "GATEWAY_PAGAMENTO_SIMULADO"
    status: str = "PENDENTE"
    id_transacao_externa: Optional[str] = None
    atualizado_em: str = field(default_factory=_agora_utc_iso)


@dataclass
class LogAuditoria:
    id: int
    id_usuario: str
    perfil_usuario: str
    tipo_operacao: str
    entidade_afetada: str
    motivo: str
    valor_anterior: str
    valor_novo: str
    data_hora: str = field(default_factory=_agora_utc_iso)
