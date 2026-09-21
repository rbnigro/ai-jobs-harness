import time

# evaluation/engine.py
from google import genai
from google.genai import types
from config.environment import Config
from data_contracts.job_contracts import JobEvaluationResult


class GeminiQuotaExceededError(RuntimeError):
    """Indica que a cota do projeto Gemini foi atingida."""


def real_ai_agent(raw_job: dict, user_profile: dict) -> JobEvaluationResult:
    """
    Chama a API do Gemini de forma determinística para avaliar a vaga 
    cruzando-a semanticamente com o perfil do usuário extraído do PDF.
    """
    if not Config.GEMINI_API_KEY:
        raise ValueError("Chave de API do Gemini não configurada.")
        
    client = genai.Client(api_key=Config.GEMINI_API_KEY)
    
    # Criamos o contexto e as regras de peso do Harness para guiar o modelo
    prompt_sistema = """
    Você é o motor de avaliação de um Harness de Empregos IA-First. 
    Sua tarefa é analisar uma vaga de emprego e calcular a aderência bilateral contra o perfil do usuário.
    Calcule o score de 0.0 a 1.0 com base nos seguintes pesos:
    - 40% Stack de IA (Python, SQL, LLMs, Machine Learning) na descrição.
    - 30% Gap de competências viável para transição de carreira.
    - 20% Alinhamento com o Objetivo do usuário.
    - 10% Localização/Modelo de trabalho.
    """

    prompt_usuario = f"""
    [PERFIL DO USUÁRIO (Vindo do PDF)]
    Nome: {user_profile.get('nome')}
    Objetivo Estratégico: {user_profile.get('objetivo_ia')}
    Competências Atuais: {user_profile.get('competencias')}
    
    [DADOS BRUTOS DA VAGA]
    Título: {raw_job.get('titulo')}
    Empresa: {raw_job.get('empresa')}
    Descrição: {raw_job.get('descricao_completa')}
    """

    print(f"[IA REAL] Enviando vaga '{raw_job.get('titulo')}' ao Gemini...")

    # Chamada forçando o Structured Output baseado no nosso contrato Pydantic
    request_config = types.GenerateContentConfig(
        system_instruction=prompt_sistema,
        response_mime_type="application/json",
        response_schema=JobEvaluationResult,
        temperature=0.1,
    )

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt_usuario,
                config=request_config,
            )
            break
        except Exception as error:
            error_text = str(error)
            if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
                raise GeminiQuotaExceededError(
                    "Cota do Gemini atingida. Aguarde a renovacao da cota ou configure faturamento."
                ) from error
            is_unavailable = "503" in error_text or "UNAVAILABLE" in error_text
            if not is_unavailable or attempt == 2:
                raise
            wait_seconds = 2 ** attempt
            print(f"[IA REAL] Serviço temporariamente indisponível. Nova tentativa em {wait_seconds}s...")
            time.sleep(wait_seconds)

    # Retorna o objeto validado diretamente do JSON respondido pelo Gemini
    return JobEvaluationResult.model_validate_json(response.text)
