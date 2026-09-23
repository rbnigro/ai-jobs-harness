import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# main.py
from data_contracts.user_profile import UserProfile
from data_contracts.job_contracts import JobRawPayload
from ingestion.parse_profile import ProfileExtractor
from evaluation.engine import GeminiQuotaExceededError, real_ai_agent
from ingestion.job_sources import collect_jobs
from ingestion.search_profile import recreate_search_profile
from storage.job_registry import save_jobs_markdown

class JobHarness:
    def __init__(self, target_objective: str):
        self.objective = target_objective
        self.user_profile: UserProfile = None
        self.raw_jobs = []
        self.evaluated_jobs = []

    def load_user_profile(self, pdf_path: str):
        """Orquestra a leitura e validação do perfil do usuário"""
        extractor = ProfileExtractor(pdf_path)
        texto_bruto = extractor.extract_raw_text()
        dados_estruturados = extractor.mock_structure_profile(texto_bruto, self.objective)
        self.user_profile = UserProfile(**dados_estruturados)
        print(f"✅ Perfil carregado com sucesso para: {self.user_profile.nome}")

    def ingest_jobs(self, jobs_list: list):
        """Valida e injeta vagas no pipeline"""
        for job in jobs_list:
            self.raw_jobs.append(JobRawPayload(**job))

    def run_evaluation(self):
        """Executa a engine de IA Real contra as vagas do pipeline"""
        if not self.user_profile:
            raise ValueError("Impossível avaliar vagas sem carregar o perfil do usuário.")
            
        for job in self.raw_jobs:
            try:
                # Executa a chamada real da API usando os contratos estritos
                resultado_real = real_ai_agent(job.model_dump(), self.user_profile.model_dump())
                self.evaluated_jobs.append(resultado_real)
            except GeminiQuotaExceededError as error:
                print(f"❌ {error}")
                print("[HARNESS] Avaliacao interrompida para nao consumir mais chamadas da API.")
                break
            except Exception as e:
                print(f"❌ Falha ao avaliar vaga com o Gemini: {e}")

    def show_report(self):
        print("\n" + "="*50)
        print("📊 RELATÓRIO DO HARNESS (REAL SEMANTIC LLM EVALUATION)")
        print("="*50)
        for raw_job, evaluation in zip(self.raw_jobs, self.evaluated_jobs):
            source = self._source_name(raw_job.link_vaga)
            print(f"Vaga: {raw_job.titulo}")
            print(f"Empresa: {raw_job.empresa}")
            print(f"Fonte: {source}")
            print(f"Link da vaga: {raw_job.link_vaga}")
            print(f"Vaga ID: {evaluation.id_vaga[:12]}... | Score de Aderência: {evaluation.score_aderencia * 100}%")
            print(f"Justificativa Analítica:\n{evaluation.justificativa}")
            print(f"Gaps Técnicos Detectados: {evaluation.competencias_faltantes}")
            print(f"Plano de Ação: {evaluation.proximos_passos_sugeridos}\n")
            print("-" * 50)

    @staticmethod
    def _source_name(link: str) -> str:
        if "adzuna.com" in link:
            return "Adzuna"
        if "remoteok.com" in link:
            return "Remote OK"
        if "remotive.com" in link:
            return "Remotive"
        if "jooble.org" in link:
            return "Jooble"
        return "Fonte configurada"

if __name__ == "__main__":
    OBJETIVO = "Transição para Engenheiro de IA (Foco em LLMs e Automação)"
    PDF_CAMINHO = "ingestion/profile.pdf"

    harness = JobHarness(target_objective=OBJETIVO)
    
    try:
        harness.load_user_profile(PDF_CAMINHO)
    except FileNotFoundError as e:
        print(e)
        exit()

    recreate_search_profile(harness.user_profile)
    print("✅ Perfil de busca recriado em ingestion/search_profile.md")

    try:
        vagas = collect_jobs()
    except Exception as error:
        print(f"❌ Falha ao coletar vagas: {error}")
        exit()

    if not vagas:
        registry_path = save_jobs_markdown([])
        print(f"✅ Registro das vagas salvas em: {registry_path}")
        print("Nenhuma vaga encontrada nas fontes habilitadas. "
              "Confira as mensagens [FONTE] acima e os filtros de busca no .env.")
        exit()

    max_jobs = max(1, int(os.getenv("JOB_MAX_RESULTS", "10")))
    if len(vagas) > max_jobs:
        print(f"[HARNESS] Limitando processamento a {max_jobs} vagas para controlar o uso da API.")
        vagas = vagas[:max_jobs]

    registry_path = save_jobs_markdown([job.model_dump() for job in vagas])
    print(f"✅ Registro das vagas salvas em: {registry_path}")

    harness.ingest_jobs([job.model_dump() for job in vagas])

    # Processamento Cognitivo e Relatório
    harness.run_evaluation()
    harness.show_report()
