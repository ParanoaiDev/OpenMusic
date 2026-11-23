from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


class SameHost(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if target.scheme != "https" or target.hostname != urlsplit(req.full_url).hostname:
            raise HTTPError(newurl, code, "redirect to another host", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


opener = build_opener(SameHost())


def page(url, limit, timeout=15, agent=AGENT):
    """The first `limit` bytes of a public page as text. Network errors are left to the caller to word."""
    request = Request(url, headers={"User-Agent": agent, "Accept-Language": "en"})
    with opener.open(request, timeout=timeout) as response:
        return response.read(limit).decode("utf-8", "replace")


def steady(url, limit, timeout=15, agent=AGENT):
    """page(), asked once more when the connection fails: a handshake that times out once usually
    works the second time. An HTTP error is an answer, so it is not asked again."""
    try:
        return page(url, limit, timeout, agent)
    except HTTPError:
        raise
    except OSError:
        return page(url, limit, timeout, agent)
