"""Cliente Elasticsearch autenticado com Kerberos/SPNEGO e validação mútua."""
import os
from urllib.parse import quote
import requests
from requests_gssapi import HTTPSPNEGOAuth, REQUIRED


class ElasticsearchHTTPError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Elasticsearch HTTP {status_code}: {message}")


class _Indices:
    def __init__(self, client):
        self.client = client

    def exists(self, index: str) -> bool:
        response = self.client._request("HEAD", f"/{quote(index, safe='')}", allow_status=(404,))
        return response.status_code == 200

    def create(self, index: str, settings=None, mappings=None):
        payload = {}
        if settings is not None:
            payload["settings"] = settings
        if mappings is not None:
            payload["mappings"] = mappings
        return self.client._request("PUT", f"/{quote(index, safe='')}", json=payload).json()


class KerberosElasticsearch:
    """Subset do cliente Elasticsearch usado pela API e pelo worker."""
    def __init__(self, url=None, request_timeout=10):
        self.url = (url or os.getenv("ELASTIC_URL", "https://elasticsearch:9200")).rstrip("/")
        self.timeout = request_timeout
        ca = os.getenv("ELASTIC_CA_CERTS", "/etc/elasticsearch/certs/ca.crt")
        self.session = requests.Session()
        self.session.auth = HTTPSPNEGOAuth(mutual_authentication=REQUIRED, opportunistic_auth=True)
        self.session.verify = ca
        self.indices = _Indices(self)

    def _request(self, method, path, *, json=None, params=None, allow_status=()):
        response = self.session.request(method, self.url + path, json=json, params=params, timeout=self.timeout)
        if response.status_code >= 400 and response.status_code not in allow_status:
            raise ElasticsearchHTTPError(response.status_code, response.text[:1000])
        return response

    def ping(self) -> bool:
        return self._request("HEAD", "/", allow_status=(401,)).status_code == 200

    def search(self, index: str, body=None, **kwargs):
        payload = dict(body or {})
        payload.update(kwargs)
        return self._request("POST", f"/{quote(index, safe='')}/_search", json=payload).json()

    def get(self, index: str, id: str):
        return self._request("GET", f"/{quote(index, safe='')}/_doc/{quote(str(id), safe='')}").json()

    def exists(self, index: str, id: str) -> bool:
        return self._request("HEAD", f"/{quote(index, safe='')}/_doc/{quote(str(id), safe='')}", allow_status=(404,)).status_code == 200

    def mget(self, index: str, ids):
        return self._request("POST", f"/{quote(index, safe='')}/_mget", json={"ids": list(ids)}).json()

    def index(self, index: str, id: str, document: dict, refresh=None):
        params = {"refresh": refresh} if refresh else None
        return self._request("PUT", f"/{quote(index, safe='')}/_doc/{quote(str(id), safe='')}", json=document, params=params).json()
