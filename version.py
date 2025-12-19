"""
Gerenciamento de versão do CSData Studio
Formato: YY.MM.DD rev.X
"""
from datetime import datetime

class Version:
    MAJOR = 25  # Ano (YY)
    MINOR = 12   # Mês (MM)
    PATCH = 17  # Dia (DD)
    REVISION = 2  # Revisão
    
    @classmethod
    def get_version(cls) -> str:
        """Retorna a versão no formato YY.MM.DD rev.X"""
        return f"{cls.MAJOR:02d}.{cls.MINOR:02d}.{cls.PATCH:02d} rev.{cls.REVISION}"
    
    @classmethod
    def get_full_name(cls) -> str:
        """Retorna o nome completo com versão"""
        return f"CSData Studio v{cls.get_version()}"
    
    @classmethod
    def increment_revision(cls):
        """Incrementa a revisão"""
        cls.REVISION += 1
    
    @classmethod
    def update_date(cls):
        """Atualiza para a data atual"""
        now = datetime.now()
        cls.MAJOR = now.year % 100
        cls.MINOR = now.month
        cls.PATCH = now.day

# Informações adicionais
APP_NAME = "CSData Studio"
COMPANY_NAME = "CEOSoftware"
COPYRIGHT = f"© {datetime.now().year} CEOSoftware. Todos os direitos reservados."
DESCRIPTION = "Sistema de Business Intelligence e Análise de Dados"

__version__ = Version.get_version()
__all__ = ['Version', 'APP_NAME', 'COMPANY_NAME', 'COPYRIGHT', 'DESCRIPTION']