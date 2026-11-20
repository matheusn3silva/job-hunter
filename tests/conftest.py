import httpx
import pytest


@pytest.fixture
def make_client():
    """Fábrica de cliente HTTP falso: responde `payload` sem usar a internet.

    `client.requests` guarda as requisições feitas, para os testes conferirem.
    """

    def _make(payload=None, status=200):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(status, json=payload)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        client.requests = requests
        return client

    return _make