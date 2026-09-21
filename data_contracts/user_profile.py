# data_contracts/user_profile.py
from typing import List, Optional
from pydantic import BaseModel, Field

class UserProfile(BaseModel):
    """Representa o perfil estruturado do usuário extraído do LinkedIn"""
    nome: str
    titulo_atual: str
    resumo: Optional[str] = None
    experiencias: List[str] = Field(default_factory=list, description="Lista de cargos e empresas anteriores")
    competencias: List[str] = Field(default_factory=list, description="Hard e Soft skills listadas")
    formacao: List[str] = Field(default_factory=list, description="Cursos e graduações")
    cargos_busca: List[str] = Field(default_factory=list, description="Cargos usados para buscar vagas")
    
    # Campo estratégico de direcionamento para a IA
    objetivo_ia: str = Field(..., description="O foco da transição do usuário (ex: IA Técnica ou IA Produto)")
