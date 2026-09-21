import uuid
from typing import List
from pydantic import BaseModel, Field

class JobRawPayload(BaseModel):
    """Garante a estrutura do dado bruto capturado das vagas"""
    id_vaga: str = Field(default_factory=lambda: str(uuid.uuid4()))
    titulo: str
    empresa: str
    localizacao: str
    descricao_completa: str
    link_vaga: str

class JobEvaluationResult(BaseModel):
    """Estrutura de saída do módulo de IA após avaliar a vaga"""
    id_vaga: str
    score_aderencia: float
    justificativa: str
    competencias_faltantes: List[str]
    proximos_passos_sugeridos: str
