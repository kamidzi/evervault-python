from .http.cert import Cert
from .http.relay import Relay
from .http.request import Request
from .crypto.client import Client as CryptoClient
from .models.cage_list import CageList
from .datatypes.map import ensure_is_integer

class Client(object):
    def __init__(
        self,
        api_key=None,
        request_timeout=30,
        base_url="https://api.evervault.com/",
        base_run_url="https://run.evervault.com/",
        relay_url="https://relay.evervault.com:443",
        ca_host="https://ca.evervault.com",
        retry=False,
        curve="SECP256K1",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.base_run_url = base_run_url
        self.relay_url = relay_url
        self.ca_host = ca_host
        request = Request(self.api_key, request_timeout, retry)
        cert = Cert(request, ca_host, base_run_url, base_url, api_key, relay_url)
        self.relay = Relay(request, base_run_url, base_url, cert)
        self.crypto_client = CryptoClient(api_key, curve)

    @property
    def _auth(self):
        return (self.api_key, "")

    def encrypt(self, data):
        return self.crypto_client.encrypt_data(self, data)

    def run(self, cage_name, data, options={"async": False, "version": None}):
        optional_headers = self.__build_cage_run_headers(options)
        return self.post(cage_name, data, optional_headers, True)

    def encrypt_and_run(
        self, cage_name, data, options={"async": False, "version": None}
    ):
        encrypted_data = self.encrypt(data)
        return self.run(cage_name, encrypted_data, options)

    def cages(self):
        cages = self.get("cages")["cages"]
        return CageList(cages, self).cages

    def relay(self, ignore_domains=[]):
        self.relay.setup(ignore_domains)

    def get(self, path, params={}):
        self.relay.get(path, params)

    def post(self, path, params, optional_headers, cage_run=False):
        self.relay.post(path, params, optional_headers, cage_run)

    def put(self, path, params):
        self.relay.put(path, params)

    def delete(self, path, params):
        self.relay.delete(path, params)

    def __build_cage_run_headers(self, options):
        if options is None:
            return {}
        cage_run_headers = {}
        if "async" in options:
            if options["async"]:
                cage_run_headers["x-async"] = "true"
            options.pop("async", None)
        if "version" in options:
            if ensure_is_integer(options["version"]):
                cage_run_headers["x-version-id"] = str(int(float(options["version"])))
            options.pop("version", None)
        cage_run_headers.update(options)
        return cage_run_headers
