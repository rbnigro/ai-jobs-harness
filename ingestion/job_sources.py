import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from email.parser import BytesParser
from xml.etree import ElementTree

import requests

from data_contracts.job_contracts import JobRawPayload
from .filters import matches_query
from .source_utils import validate_source_url, _job, _HtmlTextParser

class RssJobSource:
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()

    def fetch(self, feed_url: str) -> list[JobRawPayload]:
        validate_source_url(feed_url)
        response = self.session.get(feed_url, timeout=20, headers={"User-Agent": "AIJobsHarness/1.0"})
        response.raise_for_status()
        root = ElementTree.fromstring(response.content) # type: ignore
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
        from email import policy
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
        import urllib.robotparser
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
    """Orquestra a coleta de vagas de todas as fontes habilitadas."""
    jobs: list[JobRawPayload] = []
    query = os.getenv("JOB_QUERY", "AI Engineer")

    # 1. Coleta do Remote OK
    try:
        remote_ok = RemoteOkSource()
        fetched_remote = remote_ok.fetch(query)
        jobs.extend(fetched_remote)
        print(f"[FONTE] Remote OK: {len(fetched_remote)} vagas coletadas.")
    except Exception as e:
        print(f"[FONTE] Erro ao coletar do Remote OK: {e}")

    # 2. Coleta do Remotive
    try:
        remotive = RemotiveSource()
        fetched_remotive = remotive.fetch(query)
        jobs.extend(fetched_remotive)
        print(f"[FONTE] Remotive: {len(fetched_remotive)} vagas coletadas.")
    except Exception as e:
        print(f"[FONTE] Erro ao coletar do Remotive: {e}")

    # 3. Coleta do Adzuna (se as credenciais estiverem no .env)
    adzuna_app_id = os.getenv("ADZUNA_APP_ID")
    adzuna_app_key = os.getenv("ADZUNA_APP_KEY")
    if adzuna_app_id and adzuna_app_key:
        try:
            adzuna = AdzunaSource(
                app_id=adzuna_app_id,
                app_key=adzuna_app_key,
                country=os.getenv("ADZUNA_COUNTRY", "br")
            )
            fetched_adzuna = adzuna.fetch(query=query, location=os.getenv("ADZUNA_LOCATION", ""))
            jobs.extend(fetched_adzuna)
            print(f"[FONTE] Adzuna: {len(fetched_adzuna)} vagas coletadas.")
        except Exception as e:
            print(f"[FONTE] Erro ao coletar do Adzuna: {e}")

    return jobs