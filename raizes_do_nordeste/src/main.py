import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from src.api.controller import ControladorAPI
from src.application.use_cases import ControladorCasoDeUso
from src.infrastructure.repositories_and_services import (
    GatewayPagamento,
    RepositorioBD,
    ServicoAutenticacao,
)

repositorio_dados = RepositorioBD()
gateway_pagamento = GatewayPagamento()
servico_aplicacao = ControladorCasoDeUso(
    repositorio_dados, gateway_pagamento
)
controlador_api = ControladorAPI(servico_aplicacao)


class ManipuladorRequisicoes(BaseHTTPRequestHandler):
    def _processar_requisicao(self, metodo_http: str):
        url_analisada = urlparse(self.path)
        parametros_consulta = {
            chave: valor[0]
            for chave, valor in parse_qs(url_analisada.query).items()
        }
        tamanho_corpo = int(self.headers.get("Content-Length", 0))
        corpo_json = (
            json.loads(self.rfile.read(tamanho_corpo).decode("utf-8"))
            if tamanho_corpo > 0
            else {}
        )
        cabecalhos_http = {
            chave: valor for chave, valor in self.headers.items()
        }

        codigo_status, corpo_resposta = controlador_api.processar_requisicao(
            metodo=metodo_http,
            caminho=url_analisada.path,
            headers=cabecalhos_http,
            body=corpo_json,
            query=parametros_consulta,
        )
        self.send_response(codigo_status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        resposta_serializada = json.dumps(
            corpo_resposta, ensure_ascii=False, indent=2
        ).encode("utf-8")
        self.wfile.write(resposta_serializada)

    def do_GET(self):
        self._processar_requisicao("GET")

    def do_POST(self):
        self._processar_requisicao("POST")

    def do_PATCH(self):
        self._processar_requisicao("PATCH")


if __name__ == "__main__":
    print("=== API Raízes do Nordeste iniciada em http://localhost:8000 ===")
    print("Tokens JWT de demonstração (RBAC):")
    usuarios_demonstracao = [
        ("cliente1", "CLIENTE", None),
        ("funcionario1", "ATENDENTE", 1),
        ("funcionario2", "COZINHEIRO", 1),
        ("funcionario3", "GERENTE", 1),
        ("colaborador1", "MATRIZ", None),
    ]
    for identificador, perfil, unidade in usuarios_demonstracao:
        token_gerado = ServicoAutenticacao.gerar_token(
            identificador, perfil, unidade
        )
        print(f"  {perfil} ({identificador}): Bearer {token_gerado}")
    servidor_http = HTTPServer(("0.0.0.0", 8000), ManipuladorRequisicoes)
    servidor_http.serve_forever()
