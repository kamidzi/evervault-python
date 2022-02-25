from datetime import datetime
from urllib.parse import urlparse

import OpenSSL
import requests
import warnings
import certifi
import tempfile

from evervault.errors.evervault_errors import CertDownloadError


class Cert(object):
    def __init__(self, request, ca_host, base_run_url, base_url, api_key, relay_url):
        self.relay_url = relay_url
        self.api_key = api_key
        self.base_url = base_url
        self.base_run_url = base_run_url
        self.request = request
        self.ca_host = ca_host
        self.cert_content = None
        self.expire_date = None

    def is_certificate_expired(self):
        if self.expire_date is not None:
            now = datetime.utcnow().timestamp()
            if now > self.expire_date.timestamp():
                return True
        return False

    def update_certificate(self):
        abc = "abc"

    def setup(client_self, ignore_domains=[]):
        ignore_domains.append(urlparse(client_self.base_run_url).netloc)
        ignore_domains.append(urlparse(client_self.base_url).netloc)
        ignore_domains.append(urlparse(client_self.ca_host).netloc)
        ignore_if_exact = []
        ignore_if_endswith = ()
        for domain in ignore_domains:
            if domain.startswith("www."):
                domain = domain[4:]
            ignore_if_exact.append(domain)
            ignore_if_endswith += ("." + domain, "@" + domain)
        old_request_func = requests.Session.request

        cert_path = client_self.__get_cert()

        api_key = client_self.api_key
        relay_url = client_self.relay_url

        # We override this method to stop the requests library from
        # removing the API token from the Proxy-Authorization header
        def rebuild_proxies(self, prepared_request, proxies):
            pass

        requests.sessions.SessionRedirectMixin.rebuild_proxies = rebuild_proxies

        def new_req_func(
            self,
            method,
            url,
            params=None,
            data=None,
            headers={},
            cookies=None,
            files=None,
            auth=None,
            timeout=None,
            allow_redirects=True,
            proxies={},
            hooks=None,
            stream=None,
            verify=None,
            cert=None,
            json=None,
        ):
            if headers is None:
                headers = {}
            if proxies is None:
                proxies = {}
            headers["Proxy-Authorization"] = api_key
            proxies["https"] = relay_url
            verify = cert_path
            try:
                domain = urlparse(url).netloc
                if domain in ignore_if_exact or domain.endswith(ignore_if_endswith):
                    del headers["Proxy-Authorization"]
                    del proxies["https"]
            except Exception:
                warnings.warn(
                    f"Unable to parse {url} when attempting to check "
                    "if it is an ignore_domain."
                )
                pass
            return old_request_func(
                self,
                method,
                url,
                params,
                data,
                headers,
                cookies,
                files,
                auth,
                timeout,
                allow_redirects,
                proxies,
                hooks,
                stream,
                verify,
                cert,
                json,
            )

        requests.Session.request = new_req_func

    def __get_cert(self):
        ca_content = None
        i = 0

        while ca_content is None and i < 2:
            i += 1
            try:
                ca_content = self.request.make_request(
                    "GET", self.ca_host, {}, _is_ca=True
                ).content
            except:  # noqa: E722
                pass

        if ca_content is None:
            raise CertDownloadError(
                f"Unable to install the Evervault root certificate from {self.ca_host}. "
            )

        self.__set_cert_expire_date(ca_content)

        try:
            with tempfile.NamedTemporaryFile(delete=False) as cert_file:
                cert_file.write(bytes(certifi.contents(), "ascii") + ca_content)
                cert_path = cert_file.name
        except:
            raise CertDownloadError(
                f"Unable to install the Evervault root certficate from {self.ca_host}. "
                "Likely a permissions error when attempting to write to the /tmp/ directory."
            )

        return cert_path

    def __set_cert_expire_date(self, ca_content):
        try:
            cert_info = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, ca_content)
            not_after = cert_info.get_notAfter().decode('utf-8')
            self.expire_date = datetime.strptime(not_after, '%Y%m%d%H%M%S%z')
            # self.exp_day = cert_info[6:8].decode('utf-8')
            # self.exp_month = cert_info[4:6].decode('utf-8')
            # self.exp_year = cert_info[:4].decode('utf-8')
        except:
            self.expire_date = None
            # self.exp_day = None
            # self.exp_month = None
            # self.exp_year = None