from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def save_jobs_markdown(jobs: Iterable[dict[str, Any]], output_path: str | Path | None = None) -> Path:
    """Persiste as vagas encontradas em um arquivo Markdown legível."""
    jobs_list = list(jobs)
    target = Path(output_path) if output_path is not None else Path("storage") / "jobs_found.md"
    target.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: list[str] = [
        "# Vagas encontradas",
        "",
        f"_Gerado em: {timestamp}_",
        "",
        f"_Total de vagas: {len(jobs_list)}_",
        "",
    ]

    if not jobs_list:
        lines.append("Nenhuma vaga foi encontrada nas fontes habilitadas.")
    else:
        for index, job in enumerate(jobs_list, start=1):
            title = str(job.get("titulo") or "Vaga sem título")
            company = str(job.get("empresa") or "Empresa não informada")
            location = str(job.get("localizacao") or "Localização não informada")
            link = str(job.get("link_vaga") or "Link não informado")
            description = str(job.get("descricao_completa") or "Descrição não informada")

            lines.extend([
                f"## {index}. {title}",
                "",
                f"- Empresa: {company}",
                f"- Localização: {location}",
                f"- Link: [{link}]({link})",
                "",
                "### Descrição",
                description[:2000],
                "",
                "---",
                "",
            ])

    target.write_text("\n".join(lines), encoding="utf-8")
    return target
