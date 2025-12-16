"""
Setup script para CSData Studio
Facilita a instalação e configuração inicial
"""
import os
import sys
import subprocess
from pathlib import Path

def print_header(text):
    """Imprime cabeçalho formatado"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")

def check_python_version():
    """Verifica versão do Python"""
    print_header("Verificando Versão do Python")
    
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8 ou superior é necessário!")
        return False
    
    print("✅ Versão do Python adequada")
    return True

def create_directories():
    """Cria diretórios necessários"""
    print_header("Criando Estrutura de Diretórios")
    
    dirs = [
        r"C:\CEOSoftware",
        os.path.join(os.environ.get('APPDATA', ''), 'CSDataStudio'),
        os.path.join(os.environ.get('APPDATA', ''), 'CSDataStudio', 'exports'),
        os.path.join(os.environ.get('APPDATA', ''), 'CSDataStudio', 'logs'),
    ]
    
    for directory in dirs:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ {directory}")
        except Exception as e:
            print(f"❌ Erro ao criar {directory}: {e}")

def create_config_file():
    """Cria arquivo de configuração XML"""
    print_header("Configurando Arquivo XML")
    
    config_path = r"C:\CEOSoftware\CSLogin.xml"
    
    if os.path.exists(config_path):
        response = input(f"Arquivo {config_path} já existe. Sobrescrever? (s/n): ")
        if response.lower() != 's':
            print("⏭️  Pulando criação do arquivo de configuração")
            return
    
    # Solicita informações
    print("\nPor favor, forneça as informações do banco de dados:")
    
    db_type = input("Tipo do banco (padrão: MSSQL): ").strip() or "MSSQL"
    server_name = input("Nome do servidor (padrão: localhost): ").strip() or "localhost"
    db_name = input("Nome do banco (padrão: BDCEOSOFTWARE): ").strip() or "BDCEOSOFTWARE"
    
    xml_content = f"""<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <database>
    <type>{db_type}</type>
    <name>{db_name}</name>
    <server>{server_name}</server>
  </database>
</configuration>
"""
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        print(f"✅ Arquivo criado: {config_path}")
    except Exception as e:
        print(f"❌ Erro ao criar arquivo: {e}")

def install_requirements():
    """Instala dependências do requirements.txt"""
    print_header("Instalando Dependências")
    
    req_file = "requirements.txt"
    
    if not os.path.exists(req_file):
        print(f"❌ Arquivo {req_file} não encontrado!")
        return False
    
    try:
        print("Instalando pacotes do pip...")
        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            req_file,
            "--upgrade"
        ])
        print("✅ Dependências instaladas com sucesso")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao instalar dependências: {e}")
        return False

def check_odbc_driver():
    """Verifica se o ODBC Driver está instalado"""
    print_header("Verificando ODBC Driver")
    
    try:
        import pyodbc
        drivers = pyodbc.drivers()
        
        odbc_17 = any("ODBC Driver 17" in d for d in drivers)
        odbc_18 = any("ODBC Driver 18" in d for d in drivers)
        
        if odbc_17 or odbc_18:
            print("✅ ODBC Driver for SQL Server encontrado")
            print(f"   Drivers disponíveis: {', '.join(drivers)}")
            return True
        else:
            print("⚠️  ODBC Driver 17/18 for SQL Server não encontrado")
            print("   Baixe em: https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server")
            return False
    except ImportError:
        print("⚠️  pyodbc não instalado ainda (será instalado com as dependências)")
        return True
    except Exception as e:
        print(f"⚠️  Erro ao verificar ODBC: {e}")
        return True

def create_shortcut():
    """Cria atalho na área de trabalho (Windows)"""
    print_header("Criando Atalho")
    
    if sys.platform != 'win32':
        print("⏭️  Criação de atalho disponível apenas no Windows")
        return
    
    try:
        import winshell
        from win32com.client import Dispatch
        
        desktop = winshell.desktop()
        path = os.path.join(desktop, "CSData Studio.lnk")
        target = sys.executable
        wDir = os.getcwd()
        icon = target
        arguments = os.path.join(wDir, "main.py")
        
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(path)
        shortcut.Targetpath = target
        shortcut.Arguments = f'"{arguments}"'
        shortcut.WorkingDirectory = wDir
        shortcut.IconLocation = icon
        shortcut.save()
        
        print(f"✅ Atalho criado: {path}")
    except ImportError:
        print("⏭️  Módulos para criar atalho não disponíveis")
        print("   Execute: pip install winshell pywin32")
    except Exception as e:
        print(f"⚠️  Erro ao criar atalho: {e}")

def test_connection():
    """Testa conexão com o banco"""
    print_header("Testando Conexão com Banco")
    
    try:
        from config_manager import ConfigManager
        config = ConfigManager.read_config()
        
        if not config:
            print("❌ Não foi possível ler arquivo de configuração")
            return False
        
        print(f"Tipo: {config.db_type}")
        print(f"Servidor: {config.server_name}")
        print(f"Banco: {config.db_name}")
        
        response = input("\nDeseja testar a conexão? (s/n): ")
        if response.lower() == 's':
            from authentication import get_db_connection
            conn = get_db_connection()
            print("✅ Conexão estabelecida com sucesso!")
            conn.close()
            return True
        else:
            print("⏭️  Teste de conexão pulado")
            return True
            
    except Exception as e:
        print(f"❌ Erro ao testar conexão: {e}")
        return False

def main():
    """Função principal do setup"""
    print("\n" + "="*60)
    print("  CSData Studio - Setup e Configuração")
    print("  Versão 25.01.15 rev.1")
    print("="*60)
    
    # Verifica Python
    if not check_python_version():
        sys.exit(1)
    
    # Verifica ODBC
    check_odbc_driver()
    
    # Cria diretórios
    create_directories()
    
    # Cria arquivo de configuração
    create_config_file()
    
    # Instala dependências
    if not install_requirements():
        print("\n⚠️  Houve erros na instalação de dependências")
        response = input("Deseja continuar? (s/n): ")
        if response.lower() != 's':
            sys.exit(1)
    
    # Cria atalho
    create_shortcut()
    
    # Testa conexão
    test_connection()
    
    print_header("Setup Concluído!")
    print("✅ CSData Studio está pronto para uso")
    print("\nPara iniciar o aplicativo, execute:")
    print("  python main.py")
    print("\n" + "="*60)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup cancelado pelo usuário")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)