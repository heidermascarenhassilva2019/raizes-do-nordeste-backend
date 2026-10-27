import base64
import hashlib
import hmac
import json
import sqlite3
from typing import Dict, List, Optional
from src.domain.entities import (
    Cliente,
    ConsentimentoLGPD,
    ErroRegraDeNegocio,
    EstoqueUnidade,
    LogAuditoria,
    Pagamento,
    Pedido,
    PermissaoNegada,
    Produto,
    Unidade,
)


def gerar_hash_senha(senha_plana: str) -> str:
    """Gera hash SHA-256 com salt para armazenamento seguro de senhas (LGPD)."""
    salt = "raizes-nordeste-salt-2026"
    return hashlib.sha256(f"{salt}:{senha_plana}".encode("utf-8")).hexdigest()


class ServicoAutenticacao:
    """Camada 4 (Infraestrutura): Serviço de autenticação e controle de acesso."""

    CHAVE_SECRETA_HMAC = b"raizes-do-nordeste-secret-key-2026"

    USUARIOS_CADASTRADOS = {
        "cliente1@raizes.com": {
            "senha_hash": gerar_hash_senha("123"),
            "usuario_id": "cliente1",
            "perfil": "CLIENTE",
            "unidade": None,
        },
        "funcionario1@raizes.com": {
            "senha_hash": gerar_hash_senha("123"),
            "usuario_id": "funcionario1",
            "perfil": "ATENDENTE",
            "unidade": 1,
        },
        "funcionario2@raizes.com": {
            "senha_hash": gerar_hash_senha("123"),
            "usuario_id": "funcionario2",
            "perfil": "COZINHEIRO",
            "unidade": 1,
        },
        "funcionario3@raizes.com": {
            "senha_hash": gerar_hash_senha("123"),
            "usuario_id": "funcionario3",
            "perfil": "GERENTE",
            "unidade": 1,
        },
        "colaborador1@raizes.com": {
            "senha_hash": gerar_hash_senha("123"),
            "usuario_id": "colaborador1",
            "perfil": "MATRIZ",
            "unidade": None,
        },
    }

    @classmethod
    def autenticar_login(cls, email: str, senha: str) -> dict:
        if not email or "@" not in str(email):
            raise ErroRegraDeNegocio(
                "Formato de e-mail inválido.",
                400,
                "FORMATO_INVALIDO",
                [{"field": "email", "issue": "Informe um e-mail válido"}],
            )
        usuario_encontrado = cls.USUARIOS_CADASTRADOS.get(email)
        senha_informada_hash = gerar_hash_senha(str(senha or ""))
        if (
            not usuario_encontrado
            or not hmac.compare_digest(
                usuario_encontrado["senha_hash"], senha_informada_hash
            )
        ):
            mensagem_erro = (
                "Credenciais inválidas (e-mail ou senha incorretos)."
            )
            raise PermissaoNegada(
                mensagem_erro, 401, "CREDENCIAIS_INVALIDAS"
            )
        token_jwt = cls.gerar_token(
            usuario_encontrado["usuario_id"],
            usuario_encontrado["perfil"],
            usuario_encontrado["unidade"],
        )
        return {
            "accessToken": token_jwt,
            "tokenType": "Bearer",
            "expiresIn": 3600,
            "perfil": usuario_encontrado["perfil"],
            "usuarioId": usuario_encontrado["usuario_id"],
        }

    @classmethod
    def gerar_token(
        cls,
        usuario_id: str,
        perfil: str,
        id_unidade: Optional[int] = None,
    ) -> str:
        dados_token = {
            "usuario_id": usuario_id,
            "perfil": perfil,
            "unidade": id_unidade,
        }
        json_bytes = json.dumps(dados_token).encode()
        corpo_base64 = (
            base64.urlsafe_b64encode(json_bytes).decode().rstrip("=")
        )
        assinatura_hmac = hmac.new(
            cls.CHAVE_SECRETA_HMAC, corpo_base64.encode(), hashlib.sha256
        ).hexdigest()
        return f"{corpo_base64}.{assinatura_hmac}"

    @classmethod
    def validar_token(
        cls,
        token: Optional[str],
        perfis_permitidos: Optional[List[str]] = None,
    ) -> dict:
        if not token or "." not in token:
            raise PermissaoNegada(
                "Token de autenticação ausente ou malformado.",
                401,
                "TOKEN_AUSENTE_OU_INVALIDO",
            )
        corpo_base64, assinatura_recebida = token.split(".", 1)
        assinatura_esperada = hmac.new(
            cls.CHAVE_SECRETA_HMAC, corpo_base64.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(assinatura_recebida, assinatura_esperada):
            raise PermissaoNegada(
                "Assinatura do token inválida.", 401, "TOKEN_INVALIDO"
            )
        preenchimento_base64 = "=" * (-len(corpo_base64) % 4)
        json_decodificado = base64.urlsafe_b64decode(
            corpo_base64 + preenchimento_base64
        ).decode()
        dados_usuario = json.loads(json_decodificado)
        perfil_atual = dados_usuario.get("perfil")
        if perfis_permitidos and perfil_atual not in perfis_permitidos:
            mensagem_erro = (
                f"Perfil '{perfil_atual}' não possui permissão. "
                f"Exigido: {perfis_permitidos}."
            )
            raise PermissaoNegada(mensagem_erro, 403, "PERMISSAO_NEGADA")
        return dados_usuario


class GatewayPagamento:
    """Camada 4 (Infraestrutura): Serviço simulado de pagamento externo (aprovação, recusa ou falha)."""

    def __init__(self):
        self.transacoes_processadas: Dict[str, dict] = {}
        self.indisponivel: bool = False

    def processar_pagamento_simulado(
        self, chave_idempotencia: str, valor: float, dados_pagamento: dict
    ) -> dict:
        # Rejeita dados sensíveis de cartão (número ou CVV) no sistema principal
        if "numero_cartao" in dados_pagamento or "cvv" in dados_pagamento:
            mensagem_erro = (
                "Violação de segurança: o sistema principal não aceita "
                "PAN/CVV brutos. Utilize token_pagamento."
            )
            raise ErroRegraDeNegocio(
                mensagem_erro, 400, "DADOS_CARTAO_NAO_PERMITIDOS"
            )
        # Evita cobrança duplicada retornando a transação já processada para a mesma chave
        if chave_idempotencia in self.transacoes_processadas:
            return self.transacoes_processadas[chave_idempotencia]

        if self.indisponivel:
            return {
                "resultado_gateway": "FAILURE",
                "status": "ERRO_INTEGRACAO",
                "id_transacao_externa": None,
                "mensagem": "Gateway de pagamento simulado indisponível.",
            }

        token_pagamento = dados_pagamento.get(
            "token_pagamento", "tok_pagamento_aprovado"
        )
        resultado_simulado = dados_pagamento.get(
            "simularResultado", "SUCCESS"
        ).upper()
        codigo_transacao = abs(hash(chave_idempotencia)) % 1000000

        pagamento_recusado = (
            resultado_simulado == "FAILURE"
            or token_pagamento.endswith("_recusado")
            or valor <= 0
        )
        if pagamento_recusado:
            resposta_gateway = {
                "resultado_gateway": "FAILURE",
                "status": "RECUSADO",
                "id_transacao_externa": f"GW-REC-{codigo_transacao:06d}",
                "mensagem": (
                    "Pagamento recusado pelo gateway simulado (FAILURE)."
                ),
            }
        elif resultado_simulado == "PENDENTE":
            resposta_gateway = {
                "resultado_gateway": "PENDING",
                "status": "PENDENTE",
                "id_transacao_externa": f"GW-PEN-{codigo_transacao:06d}",
                "mensagem": (
                    "Cobrança registrada no gateway simulado; "
                    "aguardando confirmação via webhook."
                ),
            }
        else:
            resposta_gateway = {
                "resultado_gateway": "SUCCESS",
                "status": "APROVADO",
                "id_transacao_externa": f"GW-APR-{codigo_transacao:06d}",
                "mensagem": (
                    "Pagamento aprovado com sucesso pelo gateway simulado "
                    "(SUCCESS)."
                ),
            }

        self.transacoes_processadas[chave_idempotencia] = resposta_gateway
        return resposta_gateway


class RepositorioBD:
    """Camada 4 (Infraestrutura): Persistência relacional SQLite e cache de objetos de domínio."""

    def __init__(self, caminho_sqlite: str = ":memory:"):
        self.conexao_sqlite = sqlite3.connect(
            caminho_sqlite, check_same_thread=False
        )
        self.unidades: Dict[int, Unidade] = {}
        self.produtos: Dict[int, Produto] = {}
        self.estoques: Dict[tuple, EstoqueUnidade] = {}
        self.clientes: Dict[int, Cliente] = {}
        self.consentimentos: List[ConsentimentoLGPD] = []
        self.pedidos: Dict[int, Pedido] = {}
        self.pagamentos: Dict[int, Pagamento] = {}
        self.pagamentos_por_idempotencia: Dict[str, Pagamento] = {}
        self.webhooks_processados: set = set()
        self.logs_auditoria: List[LogAuditoria] = []
        self._sequencia_pedido = 1
        self._sequencia_pagamento = 1
        self._sequencia_auditoria = 1
        self._executar_migrations_sqlite()
        self._popular_dados_iniciais()

    def _executar_migrations_sqlite(self):
        cursor = self.conexao_sqlite.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS unidades (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL,
                cidade TEXT NOT NULL,
                regiao TEXT NOT NULL,
                tipo_cozinha TEXT NOT NULL,
                hora_abertura INTEGER NOT NULL,
                hora_fechamento INTEGER NOT NULL,
                ativa INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL,
                categoria TEXT NOT NULL,
                preco_base REAL NOT NULL,
                exige_cozinha_completa INTEGER NOT NULL,
                sazonal INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS estoques_unidade (
                id_unidade INTEGER NOT NULL,
                id_produto INTEGER NOT NULL,
                quantidade INTEGER NOT NULL,
                preco_local REAL NOT NULL,
                ativo INTEGER NOT NULL,
                PRIMARY KEY (id_unidade, id_produto)
            );
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL,
                cpf TEXT NOT NULL,
                idade INTEGER NOT NULL,
                contato TEXT NOT NULL,
                consentimento_lgpd INTEGER NOT NULL,
                saldo_pontos INTEGER NOT NULL,
                anonimizado INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY,
                id_unidade INTEGER NOT NULL,
                id_cliente INTEGER,
                canal_pedido TEXT NOT NULL,
                status TEXT NOT NULL,
                valor_bruto REAL NOT NULL,
                valor_desconto REAL NOT NULL,
                valor_total REAL NOT NULL,
                criado_em TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS logs_auditoria (
                id INTEGER PRIMARY KEY,
                id_usuario TEXT NOT NULL,
                perfil_usuario TEXT NOT NULL,
                tipo_operacao TEXT NOT NULL,
                entidade_afetada TEXT NOT NULL,
                motivo TEXT NOT NULL,
                valor_anterior TEXT NOT NULL,
                valor_novo TEXT NOT NULL,
                data_hora TEXT NOT NULL
            );
            """
        )
        self.conexao_sqlite.commit()

    def _popular_dados_iniciais(self):
        self.unidades[1] = Unidade(
            1, "Unidade 1", "Recife", "PE", "COMPLETA", 6, 22, True
        )
        self.unidades[2] = Unidade(
            2, "Unidade 2", "Salvador", "BA", "REDUZIDA", 7, 20, True
        )

        self.produtos[1] = Produto(
            1,
            "Produto 1",
            "Cuscuz",
            24.90,
            exige_cozinha_completa=False,
        )
        self.produtos[2] = Produto(
            2,
            "Produto 2",
            "Tapiocas",
            18.50,
            exige_cozinha_completa=False,
        )
        self.produtos[3] = Produto(
            3,
            "Produto 3",
            "Refeições Regionais",
            45.00,
            exige_cozinha_completa=True,
        )
        self.produtos[4] = Produto(
            4,
            "Produto 4",
            "Sazonais Juninos",
            16.00,
            exige_cozinha_completa=False,
            sazonal=True,
            meses_sazonais=[6],
        )

        self.estoques[(1, 1)] = EstoqueUnidade(1, 1, 30, 24.90, True)
        self.estoques[(1, 2)] = EstoqueUnidade(1, 2, 40, 18.50, True)
        self.estoques[(1, 3)] = EstoqueUnidade(1, 3, 15, 45.00, True)
        self.estoques[(1, 4)] = EstoqueUnidade(1, 4, 20, 16.00, True)

        self.estoques[(2, 1)] = EstoqueUnidade(2, 1, 10, 25.90, True)
        self.estoques[(2, 2)] = EstoqueUnidade(2, 2, 25, 19.00, True)
        self.estoques[(2, 3)] = EstoqueUnidade(2, 3, 5, 45.00, True)

        self.clientes[1] = Cliente(
            1,
            "Cliente 1",
            "123.456.789-00",
            34,
            "cliente1@email.com",
            consentimento_lgpd=True,
            saldo_pontos=60,
        )
        self.clientes[2] = Cliente(
            2,
            "Cliente 2",
            "987.654.321-11",
            28,
            "cliente2@email.com",
            consentimento_lgpd=False,
            saldo_pontos=0,
        )

        cursor = self.conexao_sqlite.cursor()
        for u in self.unidades.values():
            cursor.execute(
                "INSERT OR REPLACE INTO unidades VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    u.id,
                    u.nome,
                    u.cidade,
                    u.regiao,
                    u.tipo_cozinha,
                    u.hora_abertura,
                    u.hora_fechamento,
                    int(u.ativa),
                ),
            )
        for p in self.produtos.values():
            cursor.execute(
                "INSERT OR REPLACE INTO produtos VALUES (?, ?, ?, ?, ?, ?)",
                (
                    p.id,
                    p.nome,
                    p.categoria,
                    p.preco_base,
                    int(p.exige_cozinha_completa),
                    int(p.sazonal),
                ),
            )
        for est in self.estoques.values():
            cursor.execute(
                "INSERT OR REPLACE INTO estoques_unidade VALUES (?, ?, ?, ?, ?)",
                (
                    est.id_unidade,
                    est.id_produto,
                    est.quantidade,
                    est.preco_local,
                    int(est.ativo),
                ),
            )
        for cli in self.clientes.values():
            cursor.execute(
                "INSERT OR REPLACE INTO clientes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cli.id,
                    cli.nome,
                    cli.cpf,
                    cli.idade,
                    cli.contato,
                    int(cli.consentimento_lgpd),
                    cli.saldo_pontos,
                    int(cli.anonimizado),
                ),
            )
        self.conexao_sqlite.commit()

    def salvar_pedido_sqlite(self, pedido: Pedido):
        cursor = self.conexao_sqlite.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO pedidos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                pedido.id,
                pedido.id_unidade,
                pedido.id_cliente,
                pedido.canal,
                pedido.status,
                pedido.valor_bruto,
                pedido.valor_desconto,
                pedido.valor_total,
                pedido.criado_em,
            ),
        )
        self.conexao_sqlite.commit()

    def registrar_auditoria(
        self,
        id_usuario: str,
        perfil_usuario: str,
        tipo_operacao: str,
        entidade_afetada: str,
        motivo_operacao: str,
        valor_anterior: str,
        valor_novo: str,
    ):
        registro_auditoria = LogAuditoria(
            id=self._sequencia_auditoria,
            id_usuario=id_usuario,
            perfil_usuario=perfil_usuario,
            tipo_operacao=tipo_operacao,
            entidade_afetada=entidade_afetada,
            motivo=motivo_operacao,
            valor_anterior=valor_anterior,
            valor_novo=valor_novo,
        )
        self._sequencia_auditoria += 1
        self.logs_auditoria.append(registro_auditoria)
        cursor = self.conexao_sqlite.cursor()
        cursor.execute(
            "INSERT INTO logs_auditoria VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                registro_auditoria.id,
                registro_auditoria.id_usuario,
                registro_auditoria.perfil_usuario,
                registro_auditoria.tipo_operacao,
                registro_auditoria.entidade_afetada,
                registro_auditoria.motivo,
                registro_auditoria.valor_anterior,
                registro_auditoria.valor_novo,
                registro_auditoria.data_hora,
            ),
        )
        self.conexao_sqlite.commit()
        return registro_auditoria
