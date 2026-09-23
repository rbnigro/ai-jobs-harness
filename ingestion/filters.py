import re
import unicodedata
from data_contracts.job_contracts import JobRawPayload

#filters.py
def _normalize_text(value: str) -> str:
    """Normaliza o texto removendo acentos e convertendo para minúsculas."""
    if not value:
        return ""
    normalized = unicodedata.normalize("NFD", value.lower())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def matches_query(job: JobRawPayload, query: str) -> bool:
    """Verifica se a vaga corresponde aos termos de busca (suporta operadores lógicos e tokens parciais)."""
    terms = [_normalize_text(term) for term in query.split("|") if term.strip()]
    searchable = _normalize_text(f"{job.titulo} {job.descricao_completa}")

    if not terms:
        return True

    for term in terms:
        if term in searchable:
            return True

        tokens = [token for token in re.split(r"[^a-z0-9]+", term) if token]
        if len(tokens) <= 1:
            continue

        matches = sum(1 for token in tokens if token in searchable)
        if matches >= max(1, len(tokens) - 1):
            return True

    return False


def is_brazilian_compatible(location: str) -> bool:
    """Rejeita estritamente vagas no exterior, aceitando apenas Brasil ou trabalho remoto genérico."""
    normalized = " ".join((location or "").lower().split())
    normalized = _normalize_text(normalized)

    if not normalized:
        return False
    
    blocked_countries = (
        "portugal", "estados unidos", "usa", "united states", "melbourne", 
        "ireland", "cincinnati", "australia", "redwood city", "redwood", 
        "mexico", "espanha", "argentina", "canada"
    )
    
    # Se a localização contiver qualquer país ou cidade bloqueada, rejeita na hora
    if any(blocked in normalized for blocked in blocked_countries):
        return False

    brazilian_markers = (
        "brasil", "brazil", "sao paulo", "rio de janeiro", "belo horizonte", "curitiba",
        "porto alegre", "salvador", "recife", "campinas", "florianopolis", "niteroi",
        "fortaleza", "goiania", "manaus", "brasilia", "sao paulo-sp", "sp"
    )
    
    if any(marker in normalized for marker in brazilian_markers):
        return True

    # Se for remoto, mas explicitamente de outro país (ex: "remote - australia"), bloqueia
    if any(country in normalized for country in blocked_countries):
        return False

    if "remote" in normalized or "remoto" in normalized:
        return True

    return True


def has_blocked_terms(job: JobRawPayload) -> bool:
    """Verifica se a vaga contém termos proibidos (tecnologias, níveis ou cargos) no título ou descrição."""
    title = str(getattr(job, "titulo", "") or "")
    description = str(getattr(job, "descricao_completa", "") or "")
    combined = _normalize_text(f"{title} {description}")

    # Termos e palavras-chave estritas que você deseja banir
    blocked_terms = (
        "manager", "product manager", "engineering manager", ".net", 
        "junior", "jr", "pl", "pleno", "entry-level", "entry level"
    )
    
    return any(term in combined for term in blocked_terms)

def is_english_job(job: object) -> bool:
    """Desconsidera vagas em inglês puro, mas mantém vagas brasileiras remotas com Java/Spring/Backend."""
    title = str(getattr(job, "titulo", "") or "")
    company = str(getattr(job, "empresa", "") or "")
    location = str(getattr(job, "localizacao", "") or "")
    description = str(getattr(job, "descricao_completa", "") or "")
    
    combined = " ".join([title, company, location, description])
    if not combined.strip():
        return False

    normalized = _normalize_text(combined)

    brazil_markers = (
        "brazil", "brasil", "remote - brazil", "remoto - brasil", "remote brazil",
        "remoto brasil", "sao paulo", "sp", "rio de janeiro", "belo horizonte",
        "curitiba", "portugal", "brasileiro", "brasilia",
    )
    java_backend_markers = (
        "java", "spring", "spring boot", "backend", "backend engineer", "java backend",
        "java developer", "microservices", "rest api", "api rest", "java spring",
    )
    strong_portuguese_patterns = (
        "estamos buscando", "estamos contratando", "vagas para", "perfil desejado",
        "obrigatorio", "desejavel", "engenheiro", "analista", "desenvolvedor",
        "engenharia", "dados", "inteligencia artificial", "remoto", "brasil", "sao paulo",
    )

    has_brazil_context = any(marker in normalized for marker in brazil_markers)
    has_java_backend_context = any(marker in normalized for marker in java_backend_markers)
    pt_hits = sum(1 for pattern in strong_portuguese_patterns if pattern in normalized)

    if has_brazil_context and has_java_backend_context:
        return False
    
    if pt_hits >= 1 or has_brazil_context:
        return True

    return False