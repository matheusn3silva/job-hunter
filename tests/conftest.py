import httpx
import pytest


@pytest.fixture
def make_client():
    """Fábrica de cliente HTTP falso: responde `payload` sem usar a internet.

    `payload` em texto (str) vira o corpo da resposta; o resto vira JSON.

    `client.requests` guarda as requisições feitas, para os testes conferirem.
    """

    def _make(payload=None, status=200):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if isinstance(payload, str):  # RSS/HTML: corpo em texto
                return httpx.Response(status, text=payload)
            return httpx.Response(status, json=payload)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        client.requests = requests
        return client

    return _make