"""Gerenciador de configuração - stub de desenvolvimento

Este módulo fornece implementações mínimas de ConfigManager e
DatabaseConfig para permitir execução e testes locais quando o
arquivo real de configuração não estiver presente.
"""
import os
from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    db_type: str = "MSSQL"
    db_name: str = "BDCEOSOFTWARE"
    server_name: str = "localhost"

    def is_valid(self) -> bool:
        return bool(self.db_name and self.server_name)


class ConfigManager:
    """Gerenciador simples de configuração.

    Suporta sobrescrever `ConfigManager.CONFIG_PATH` (usado nos testes)
    e faz parsing básico de um arquivo XML com a estrutura esperada nos
    testes (tags <type>, <n>, <server>)."""

    # Caminho que os testes podem sobrescrever
    CONFIG_PATH: str | None = None

    DEFAULT_PATHS = [
        r"C:\\CEOSoftware\\CSLogin.xml",
        os.path.join(os.path.expanduser("~"), "CSLogin.xml"),
    ]

    @staticmethod
    def read_config(path: str | None = None) -> DatabaseConfig | None:
        import xml.etree.ElementTree as ET

        target = path or ConfigManager.CONFIG_PATH
        # Se não foi informado, tenta caminhos padrão
        if not target:
            for p in ConfigManager.DEFAULT_PATHS:
                if os.path.exists(p):
                    target = p
                    break

        if not target or not os.path.exists(target):
            # Retorna padrão se não houver arquivo
            return DatabaseConfig()

        try:
            tree = ET.parse(target)
            root = tree.getroot()

            # Primeiro, tenta encontrar o formato antigo <database>
            db = root.find("database")
            if db is not None:
                db_type = (db.findtext("type") or db.findtext("DBType") or "MSSQL").strip()
                db_name = (db.findtext("n") or db.findtext("DBName") or db.findtext("dbname") or "").strip()
                server_name = (db.findtext("server") or db.findtext("ServerName") or db.findtext("servername") or "").strip()
                return DatabaseConfig(db_type=db_type, db_name=db_name or "BDCEOSOFTWARE", server_name=server_name or "localhost")

            # Em seguida, tenta o formato usado no CSLogin.xml: <Configuracao><TipoBanco>,<NomeServidor>,<NomeBanco>
            cfgs = root.findall('.//Configuracao') or root.findall('.//configuracao')
            if cfgs:
                first = cfgs[0]
                db_type = (first.findtext('TipoBanco') or first.findtext('TipoBanco'.lower()) or first.findtext('type') or "SQLSERVER").strip()
                server_name = (first.findtext('NomeServidor') or first.findtext('nomeservidor') or first.findtext('ServerName') or "localhost").strip()
                db_name = (first.findtext('NomeBanco') or first.findtext('nomebanco') or first.findtext('name') or "BDCEOSOFTWARE").strip()

                # Normaliza alguns valores (ex: SQLSERVER -> MSSQL)
                # Preserve original TipoBanco value (e.g., 'SQLSERVER' or 'MSDE')
                return DatabaseConfig(db_type=db_type, db_name=db_name or "BDCEOSOFTWARE", server_name=server_name or "localhost")

            # Fallback: tenta extrair valores diretos do root
            db_type = (root.findtext("type") or root.findtext("DBType") or "MSSQL").strip()
            db_name = (root.findtext("n") or root.findtext("DBName") or root.findtext("dbname") or "").strip()
            server_name = (root.findtext("server") or root.findtext("ServerName") or root.findtext("servername") or "").strip()
            return DatabaseConfig(db_type=db_type, db_name=db_name or "BDCEOSOFTWARE", server_name=server_name or "localhost")
        except Exception:
            return None

    @staticmethod
    def read_all_configs(path: str | None = None) -> list:
        """Lê todas as entradas <database> do arquivo de configuração e retorna
        uma lista de DatabaseConfig. Se não encontrar arquivos, retorna uma
        lista com a configuração padrão."""
        import xml.etree.ElementTree as ET

        target = path or ConfigManager.CONFIG_PATH
        if not target:
            for p in ConfigManager.DEFAULT_PATHS:
                if os.path.exists(p):
                    target = p
                    break

        if not target or not os.path.exists(target):
            return [DatabaseConfig()]

        try:
            tree = ET.parse(target)
            root = tree.getroot()
            configs = []
            # Suporta dois formatos: <database> (antigo) e <Configuracao> (CSLogin.xml)
            for db in root.findall('.//database'):
                db_type = (db.findtext("type") or db.findtext("DBType") or "MSSQL").strip()
                db_name = (db.findtext("name") or db.findtext("n") or db.findtext("DBName") or "").strip()
                server_name = (db.findtext("server") or db.findtext("ServerName") or db.findtext("servername") or "").strip()
                configs.append(DatabaseConfig(db_type=db_type, db_name=db_name or "BDCEOSOFTWARE", server_name=server_name or "localhost"))

            # Procura elementos <Configuracao> que contêm TipoBanco/NomeServidor/NomeBanco
            for cfg in root.findall('.//Configuracao') + root.findall('.//configuracao'):
                db_type = (cfg.findtext('TipoBanco') or cfg.findtext('tipobanco') or cfg.findtext('type') or "SQLSERVER").strip()
                server_name = (cfg.findtext('NomeServidor') or cfg.findtext('nomeservidor') or cfg.findtext('ServerName') or "localhost").strip()
                db_name = (cfg.findtext('NomeBanco') or cfg.findtext('nomebanco') or cfg.findtext('name') or "BDCEOSOFTWARE").strip()

                # Preserve the raw TipoBanco / type value found in the XML
                configs.append(DatabaseConfig(db_type=db_type, db_name=db_name or "BDCEOSOFTWARE", server_name=server_name or "localhost"))

            if not configs:
                return [DatabaseConfig()]

            return configs
        except Exception:
            return [DatabaseConfig()]

    @staticmethod
    def create_sample_config(path: str | None = None) -> bool:
        target = path or ConfigManager.DEFAULT_PATHS[0]
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            sample = (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
                "<configuration>\n"
                "  <database>\n"
                "    <type>MSSQL</type>\n"
                "    <n>BDCEOSOFTWARE</n>\n"
                "    <server>localhost</server>\n"
                "  </database>\n"
                "</configuration>\n"
            )
            with open(target, "w", encoding="utf-8") as f:
                f.write(sample)
            return True
        except Exception:
            return False
