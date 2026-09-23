from html.parser import HTMLParser

from urllib.parse import urlparse

from data_contracts.job_contracts import JobRawPayload

BLOCKED_HOSTS = {"linkedin.com", "www.linkedin.com", "vagas.com.br", "www.vagas.com.br"}


def validate_source_url(url: str) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise ValueError(f"URL de fonte invalida: {url}")
    if hostname in BLOCKED_HOSTS or any(hostname.endswith(f".{host}") for host in BLOCKED_HOSTS):
        raise ValueError(f"Fonte bloqueada por seguranca: {hostname}")


def _job(title: str, company: str, location: str, description: str, link: str) -> JobRawPayload:
    return JobRawPayload(
        titulo=title.strip() or "Vaga sem titulo",
        empresa=company.strip() or "Empresa nao informada",
        localizacao=location.strip() or "Nao informada",
        descricao_completa=description.strip() or "Descricao nao informada",
        link_vaga=link.strip() or "Fonte sem link",
    )


class _HtmlTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self._in_title = False
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            key = attributes.get("name") or attributes.get("property")
            content = attributes.get("content")
            if key and content:
                self.meta[key.lower()] = content.strip()
        if tag in {"script", "style", "noscript"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        self.text_parts.append(text)

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()

    @property
    def text(self) -> str:
        return " ".join(self.text_parts).strip()