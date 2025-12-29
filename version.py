VERSION = "25.12.29 rev. 2"

# Nome amigável do aplicativo e da companhia
APP_NAME = "CSData Studio"
COMPANY_NAME = "CEOsoftware Sistemas de Informática Ltda. ®"


class Version:
	"""Classe utilitária para informações de versão do aplicativo.

	Mantemos um método estático `get_version()` para compatibilidade com
	chamadas existentes em `main.py` (ex.: Version.get_version()).
	"""

	@staticmethod
	def get_version() -> str:
		return VERSION

	def __str__(self) -> str:
		return VERSION
