import json
import time
import urllib.error
import urllib.request


class NomuraError(RuntimeError):
    pass


class NomuraClient:
    BASE_URL = "https://www.nomurafunds.com.tw/API/ETFAPI/api/Fund/"

    def __init__(self, timeout=30, retries=3):
        self.timeout = timeout
        self.retries = retries

    def post(self, endpoint, payload):
        request = urllib.request.Request(
            self.BASE_URL + endpoint,
            data=json.dumps(payload).encode(),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "nomura-etf-tracker/1.0",
            },
            method="POST",
        )
        for attempt in range(self.retries):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    result = json.load(response)
                if result.get("StatusCode") != 0:
                    raise NomuraError(
                        f"{endpoint}: API status {result.get('StatusCode')}: "
                        f"{result.get('Message', '')}"
                    )
                return result.get("Entries")
            except NomuraError:
                raise
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                if attempt + 1 == self.retries:
                    raise NomuraError(f"{endpoint}: {error}") from error
                time.sleep(2**attempt)
        raise AssertionError("unreachable")
