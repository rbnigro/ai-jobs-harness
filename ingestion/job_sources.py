import os
import re
import unicodedata
import urllib.robotparser
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests

from data_contracts.job_contracts import JobRawPayload
from ingestion.search_profile import load_search_terms


BLOCKED_HOSTS = {"linkedin.com", "www.linkedin.com", "vagas.com.br", "www.vagas.com.br"}


def configured_values(name: str) -> list[str]:
    return [value.strip() for value in os.getenv(name, "").split(",") if value.strip()]


def matches_query(job: JobRawPayload, query: str) -> bool:
    terms = [
    "".join(character for character in unicodedata.normalize("NFD", term.lower())
                if unicodedata.category(character) != "Mn")
    for term in query.split("|")
        if term.strip()
    ]
    searchable = "".join(
        character for character in unicodedata.normalize(
            "NFD", f"{job.titulo} {job.descricao_completa}".lower()
        ) if unicodedata.category(character) != "Mn"
    )
    return not terms or any(term in searchable for term in terms)


def is_brazilian_compatible(location: str) -> bool:
    """Rejeita vagas no exterior, aceitando apenas Brasil ou trabalho remoto sem país explícito."""
    normalized = " ".join((location or "").lower().split())
    normalized = "".join(
        character for character in unicodedata.normalize("NFD", normalized)
        if unicodedata.category(character) != "Mn"
    )

    if not normalized:
        return True

    foreign_markers = (
        "united states", "usa", "canada", "australia", "ireland", "uk", "united kingdom",
        "england", "germany", "france", "spain", "italy", "netherlands", "sweden", "norway",
        "denmark", "finland", "mexico", "argentina", "chile", "colombia", "peru", "uruguay",
        "panama", "ecuador", "paraguay", "bolivia", "costa rica", "guatemala", "el salvador",
        "honduras", "nicaragua", "dominican republic", "puerto rico", "portugal", "eua",
        "inglaterra", "irlanda", "mexico city",
    )
    if any(marker in normalized for marker in foreign_markers):
        return False

    brazil_markers = (
        "brasil", "brazil", "sao paulo", "rio de janeiro", "belo horizonte", "curitiba",
        "porto alegre", "salvador", "recife", "campinas", "florianopolis", "niteroi",
        "fortaleza", "goiania", "manaus", "brasilia", "sao paulo-sp", "sp"
    )
    if any(marker in normalized for marker in brazil_markers):
        return True

    if "remote" in normalized or "remoto" in normalized:
        return True

    return True


def is_english_job(job: object) -> bool:
    """Desconsidera vagas escritas em inglês com base em frases e padrões muito claros do idioma."""
    title = str(getattr(job, "titulo", "") or "")
    company = str(getattr(job, "empresa", "") or "")
    location = str(getattr(job, "localizacao", "") or "")
    description = str(getattr(job, "descricao_completa", "") or "")
    combined = " ".join([title, company, location, description]).lower()

    if not combined.strip():
        return False

    normalized = "".join(
        character for character in unicodedata.normalize("NFD", combined)
        if unicodedata.category(character) != "Mn"
    )

    strong_english_patterns = (
        "we are looking for",
        "about the role",
        "responsibilities",
        "requirements",
        "what you'll do",
        "must have",
        "ideal candidate",
        "apply now",
        "job description",
        "customer success manager",
        "senior software engineer",
        "software engineer",
        "data engineer",
        "frontend engineer",
        "full stack",
        "please mention the word",
        "you will be responsible for",
        "strong background in",
        "work with cross functional teams",
        "build scalable",
        "company is looking for",
        "hiring",
        "position",
        "team",
        "with a strong bias",
    )
    strong_portuguese_patterns = (
        "estamos buscando",
        "estamos contratando",
        "vagas para",
        "perfil desejado",
        "obrigatorio",
        "desejavel",
        "engenheiro",
        "analista",
        "desenvolvedor",
        "engenharia",
        "ciencia de dados",
        "dados",
        "inteligencia artificial",
        "remoto",
        "brasil",
        "sao paulo",
    )

    english_hits = sum(1 for pattern in strong_english_patterns if pattern in normalized)
    pt_hits = sum(1 for pattern in strong_portuguese_patterns if pattern in normalized)

    if english_hits >= 1 and pt_hits == 0:
        return True

    if english_hits >= 2:
        return True

    if english_hits >= 1 and "remote" in normalized and "brasil" not in normalized and "sao paulo" not in normalized:
        return True

    return False


def validate_source_url(url: str) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise ValueError(f"URL de fonte invalida: {url}")
    if hostname in BLOCKED_HOSTS or any(hostname.endswith(f".{host}") for host in BLOCKED_HOSTS):
        raise ValueError(f"Fonte bloqueada por seguranca: {hostname}")


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


def _job(title: str, company: str, location: str, description: str, link: str) -> JobRawPayload:
    return JobRawPayload(
        titulo=title.strip() or "Vaga sem titulo",
        empresa=company.strip() or "Empresa nao informada",
        localizacao=location.strip() or "Nao informada",
        descricao_completa=description.strip() or "Descricao nao informada",
        link_vaga=link.strip() or "Fonte sem link",
    )


class RssJobSource:
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()

    def fetch(self, feed_url: str) -> list[JobRawPayload]:
        validate_source_url(feed_url)
        response = self.session.get(feed_url, timeout=20, headers={"User-Agent": "AIJobsHarness/1.0"})
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        jobs: list[JobRawPayload] = []
        for item in root.iter():
            if item.tag.rsplit("}", 1)[-1].lower() not in {"item", "entry"}:
                continue
            fields = {child.tag.rsplit("}", 1)[-1].lower(): (child.text or "").strip() for child in item}
            link = fields.get("link", "")
            link_element = next((child for child in item if child.tag.rsplit("}", 1)[-1].lower() == "link"), None)
            if link_element is not None:
                link = link_element.attrib.get("href", link)
            jobs.append(_job(
                fields.get("title", ""),
                fields.get("author", "") or fields.get("creator", ""),
                "",
                fields.get("description", "") or fields.get("summary", "") or fields.get("content", ""),
                link,
            ))
        return jobs


class NewsletterJobSource:
    def fetch(self, file_path: str) -> list[JobRawPayload]:
        message = BytesParser(policy=policy.default).parsebytes(Path(file_path).read_bytes())
        subject = str(message.get("subject", "Vagas da newsletter"))
        body = message.get_body(preferencelist=("plain", "html"))
        content = body.get_content() if body else str(message.get_payload())
        links = re.findall(r"https?://[^\s<>\"']+", content)
        if not links:
            links = [f"newsletter://{Path(file_path).name}"]
        return [_job(subject, "Newsletter", "", content, link.rstrip(".,);")) for link in links]


class AllowlistedCrawler:
    def __init__(self, allowed_domains: list[str], session: requests.Session | None = None) -> None:
        self.allowed_domains = {domain.lower().removeprefix("www.") for domain in allowed_domains}
        self.session = session or requests.Session()

    def fetch(self, url: str) -> list[JobRawPayload]:
        validate_source_url(url)
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower().removeprefix("www.")
        if hostname not in self.allowed_domains:
            raise PermissionError(f"Dominio fora da allowlist do crawler: {hostname}")
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        robots = urllib.robotparser.RobotFileParser(robots_url)
        try:
            robots.read()
        except OSError as error:
            raise RuntimeError(f"Nao foi possivel verificar robots.txt de {parsed.netloc}") from error
        if not robots.can_fetch("AIJobsHarness/1.0", url):
            raise PermissionError(f"Crawler bloqueado pelo robots.txt: {url}")
        response = self.session.get(url, timeout=20, headers={"User-Agent": "AIJobsHarness/1.0"})
        response.raise_for_status()
        parser = _HtmlTextParser()
        parser.feed(response.text)
        description = parser.meta.get("description") or parser.text
        return [_job(parser.title, parser.meta.get("author", ""), "", description, url)]


class PartnerApiSource:
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()

    def fetch(self, url: str) -> list[JobRawPayload]:
        validate_source_url(url)
        response = self.session.get(url, timeout=20, headers={"Accept": "application/json"})
        response.raise_for_status()
        payload: Any = response.json()
        records = payload if isinstance(payload, list) else payload.get("jobs", payload.get("data", []))
        if not isinstance(records, list):
            raise ValueError(f"Resposta da API sem lista de vagas: {url}")
        return [self._to_job(record, url) for record in records if isinstance(record, dict)]

    @staticmethod
    def _to_job(record: dict[str, Any], source_url: str) -> JobRawPayload:
        return _job(
            str(record.get("titulo") or record.get("title") or record.get("name") or ""),
            str(record.get("empresa") or record.get("company") or ""),
            str(record.get("localizacao") or record.get("location") or ""),
            str(record.get("descricao_completa") or record.get("description") or record.get("summary") or ""),
            str(record.get("link_vaga") or record.get("url") or source_url),
        )


class RemoteOkSource(PartnerApiSource):
    endpoint = "https://remoteok.com/api"

    def fetch(self, query: str = "") -> list[JobRawPayload]:
        response = self.session.get(
            self.endpoint,
            timeout=20,
            headers={"Accept": "application/json", "User-Agent": "AIJobsHarness/1.0"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Resposta inesperada da API Remote OK")
        jobs = [self._to_job(record, self.endpoint) for record in payload if isinstance(record, dict) and record.get("position")]
        if query:
            jobs = [job for job in jobs if matches_query(job, query)]
        return jobs

    @staticmethod
    def _to_job(record: dict[str, Any], source_url: str) -> JobRawPayload:
        return _job(
            str(record.get("position") or ""),
            str(record.get("company") or ""),
            str(record.get("location") or "Remote"),
            str(record.get("description") or ""),
            str(record.get("url") or source_url),
        )


class RemotiveSource(PartnerApiSource):
    endpoint = "https://remotive.com/api/remote-jobs"

    def fetch(self, query: str = "") -> list[JobRawPayload]:
        response = self.session.get(
            self.endpoint,
            timeout=20,
            headers={"Accept": "application/json", "User-Agent": "AIJobsHarness/1.0"},
        )
        response.raise_for_status()
        payload = response.json()
        records = payload.get("jobs", []) if isinstance(payload, dict) else []
        jobs = [self._to_job(record, self.endpoint) for record in records if isinstance(record, dict)]
        if query:
            jobs = [job for job in jobs if matches_query(job, query)]
        return jobs

    @staticmethod
    def _to_job(record: dict[str, Any], source_url: str) -> JobRawPayload:
        return _job(
            str(record.get("title") or ""),
            str(record.get("company_name") or ""),
            str(record.get("candidate_required_location") or "Remote"),
            str(record.get("description") or ""),
            str(record.get("url") or source_url),
        )


class AdzunaSource(PartnerApiSource):
    endpoint_template = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

    def __init__(self, app_id: str, app_key: str, country: str, page: int = 1, session: requests.Session | None = None) -> None:
        super().__init__(session)
        self.app_id = app_id
        self.app_key = app_key
        self.country = country
        self.page = page

    def fetch(self, query: str = "", location: str = "") -> list[JobRawPayload]:
        endpoint = self.endpoint_template.format(country=self.country, page=self.page)
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": int(os.getenv("ADZUNA_RESULTS_PER_PAGE", "50")),
            "what": query,
            "where": location,
            "sort_by": os.getenv("ADZUNA_SORT_BY", "relevance"),
        }
        optional_params = {
            "max_days_old": os.getenv("ADZUNA_MAX_DAYS_OLD", ""),
            "distance": os.getenv("ADZUNA_DISTANCE", ""),
            "category": os.getenv("ADZUNA_CATEGORY", ""),
            "full_time": os.getenv("ADZUNA_FULL_TIME", ""),
            "part_time": os.getenv("ADZUNA_PART_TIME", ""),
            "permanent": os.getenv("ADZUNA_PERMANENT", ""),
            "contract": os.getenv("ADZUNA_CONTRACT", ""),
        }
        params.update({key: value for key, value in optional_params.items() if value != ""})
        response = self.session.get(
            endpoint,
            params=params,
            timeout=20,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "AIJobsHarness/1.0",
            },
        )
        response.raise_for_status()
        payload = response.json()
        records = payload.get("results", []) if isinstance(payload, dict) else []
        return [self._to_job(record, endpoint) for record in records if isinstance(record, dict)]

    @staticmethod
    def _to_job(record: dict[str, Any], source_url: str) -> JobRawPayload:
        location = record.get("location") or {}
        company = record.get("company") or {}
        return _job(
            str(record.get("title") or ""),
            str(company.get("display_name") if isinstance(company, dict) else company or ""),
            str(location.get("display_name") if isinstance(location, dict) else location or ""),
            str(record.get("description") or ""),
            str(record.get("redirect_url") or source_url),
        )


class JoobleSource(PartnerApiSource):
    endpoint = "https://jooble.org/api"

    def __init__(self, api_key: str, session: requests.Session | None = None) -> None:
        super().__init__(session)
        self.api_key = api_key

    def fetch(self, query: str = "", location: str = "", page: int = 1) -> list[JobRawPayload]:
        response = self.session.post(
            f"{self.endpoint}/{self.api_key}",
            json={"keywords": query, "location": location, "page": page},
            timeout=20,
            headers={"Accept": "application/json", "User-Agent": "AIJobsHarness/1.0"},
        )
        response.raise_for_status()
        payload = response.json()
        records = payload.get("jobs", []) if isinstance(payload, dict) else []
        return [self._to_job(record, self.endpoint) for record in records if isinstance(record, dict)]

    @staticmethod
    def _to_job(record: dict[str, Any], source_url: str) -> JobRawPayload:
        return _job(
            str(record.get("title") or ""),
            str(record.get("company") or ""),
            str(record.get("location") or ""),
            str(record.get("snippet") or record.get("description") or ""),
            str(record.get("link") or source_url),
        )


def collect_jobs() -> list[JobRawPayload]:
    jobs: list[JobRawPayload] = []
    rss = RssJobSource()
    newsletter = NewsletterJobSource()
    crawler = AllowlistedCrawler(configured_values("JOB_CRAWLER_ALLOWED_DOMAINS"))
    api = PartnerApiSource()
    search_roles, search_technologies = load_search_terms()
    query = "|".join(search_roles + search_technologies)
    location = os.getenv("JOB_SEARCH_LOCATION", "")

    def collect(label: str, loader: Any) -> None:
        print(f"[FONTE] Consultando {label}...")
        try:
            source_jobs = loader()
            jobs.extend(source_jobs)
            print(f"[FONTE] {label}: {len(source_jobs)} vaga(s) encontrada(s).")
        except Exception as error:
            print(f"⚠️ Fonte {label} indisponivel: {error}")

    if os.getenv("JOB_ENABLE_REMOTEOK", "false").lower() == "true":
        collect("Remote OK", lambda: RemoteOkSource().fetch(query))
    if os.getenv("JOB_ENABLE_REMOTIVE", "false").lower() == "true":
        collect("Remotive", lambda: RemotiveSource().fetch(query))

    adzuna_app_id = os.getenv("ADZUNA_APP_ID", "")
    adzuna_app_key = os.getenv("ADZUNA_APP_KEY", "")
    adzuna_enabled = os.getenv("JOB_ENABLE_ADZUNA", "true").lower() == "true"
    if adzuna_enabled and not (adzuna_app_id and adzuna_app_key):
        print("⚠️ Adzuna esta ativo, mas ADZUNA_APP_ID/ADZUNA_APP_KEY nao foram configurados.")
    if adzuna_enabled and adzuna_app_id and adzuna_app_key:
        adzuna = AdzunaSource(
                adzuna_app_id,
                adzuna_app_key,
                os.getenv("ADZUNA_COUNTRY", "br"),
                int(os.getenv("ADZUNA_PAGE", "1")),
            )
        collect("Adzuna", lambda: adzuna.fetch(query, location))

    jooble_api_key = os.getenv("JOOBLE_API_KEY", "")
    if os.getenv("JOB_ENABLE_JOOBLE", "false").lower() == "true" and jooble_api_key:
        jooble = JoobleSource(jooble_api_key)
        collect("Jooble", lambda: jooble.fetch(query, location, int(os.getenv("JOOBLE_PAGE", "1"))))

    if os.getenv("JOB_ENABLE_RSS", "false").lower() == "true":
        for url in configured_values("JOB_RSS_URLS"):
            collect(f"RSS {url}", lambda url=url: rss.fetch(url))
    if os.getenv("JOB_ENABLE_NEWSLETTER", "false").lower() == "true":
        for file_path in configured_values("JOB_NEWSLETTER_FILES"):
            collect(f"Newsletter {file_path}", lambda file_path=file_path: newsletter.fetch(file_path))
    if os.getenv("JOB_ENABLE_PARTNER_API", "false").lower() == "true":
        for url in configured_values("JOB_PARTNER_API_URLS"):
            collect(f"API {url}", lambda url=url: api.fetch(url))
    if os.getenv("JOB_ENABLE_CRAWLER", "false").lower() == "true":
        for url in configured_values("JOB_CRAWLER_URLS"):
            collect(f"Crawler {url}", lambda url=url: crawler.fetch(url))

    unique_jobs: dict[str, JobRawPayload] = {}
    for job in jobs:
        unique_jobs.setdefault(job.link_vaga, job)

    filtered = []
    rejected_foreign = 0
    rejected_english = 0

    for job in unique_jobs.values():
        if not is_brazilian_compatible(job.localizacao):
            rejected_foreign += 1
            continue
        if is_english_job(job):
            rejected_english += 1
            continue
        filtered.append(job)

    if rejected_foreign:
        print(f"[FILTRO] {rejected_foreign} vaga(s) de fora do Brasil foram descartadas.")
    if rejected_english:
        print(f"[FILTRO] {rejected_english} vaga(s) em inglês foram descartadas.")
    return filtered
