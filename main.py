"""
CSData Studio - Aplicação Principal
Sistema de Business Intelligence e Análise de Dados
"""
import sys
import os
import logging
import datetime
import json
import re
import datetime as _dt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QListWidget, QPushButton, QLabel, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QMessageBox,
    QDialog, QDialogButtonBox, QTextEdit, QCheckBox, QRadioButton,
    QGroupBox, QSplitter, QHeaderView, QFileDialog, QInputDialog,
    QProgressDialog
)
from PyQt5.QtWidgets import QMenu, QAction, QListWidgetItem
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QEvent
from PyQt5.QtGui import QIcon, QFont, QColor
from PyQt5.QtWidgets import QToolTip, QDialog, QVBoxLayout, QTextEdit
from numbers import Number

# Imports dos módulos do projeto
from version import Version, APP_NAME, COMPANY_NAME
from config_manager import ConfigManager, DatabaseConfig
from authentication import get_db_connection, verify_user
from consulta_sql import QueryBuilder, JoinType, TableInfo
from log import SessionLogger
from saved_queries import QueryManager, SavedQuery
from excecao import IMPEDING_COLUMNS
from chart_generator import ChartGenerator, ChartType, AggregationType
from ai_insights import AIInsightsGenerator
from report_generator import ReportGenerator
from valida_sql import validar_sql, validar_sql_for_save

class LoginDialog(QDialog):
    """Diálogo de login

    Agora suporta seleção do banco (lista lida de ConfigManager.read_all_configs).
    """

    def __init__(self, db_options: list | None = None, parent=None):
        super().__init__(parent)
        self.user_data = None
        self.selected_db = None
        self.db_options = db_options or []
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("Login - CSData Studio")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Título
        title = QLabel(f"<h2>{APP_NAME}</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        version_label = QLabel(f"<i>Versão {Version.get_version()}</i>")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        layout.addSpacing(20)
        # Se houver múltiplas opções de DB, exibe ComboBox
        if self.db_options:
            layout.addWidget(QLabel("Banco/Servidor:"))
            self.db_combo = QComboBox()
            for cfg in self.db_options:
                self.db_combo.addItem(f"{cfg.db_type} - {cfg.server_name} - {cfg.db_name}")
            layout.addWidget(self.db_combo)
        else:
            self.db_combo = None
        
        # Campos de login
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Usuário")
        layout.addWidget(QLabel("Usuário:"))
        layout.addWidget(self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Senha")
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(QLabel("Senha:"))
        layout.addWidget(self.password_input)

        layout.addSpacing(20)

        # Botões Ok / Cancel
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.handle_login)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)

    def handle_login(self):
        """Processa o login"""
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        # Seleciona DB escolhido primeiro
        selected_cfg = None
        if self.db_combo:
            idx = self.db_combo.currentIndex()
            selected_cfg = self.db_options[idx]
        else:
            # fallback: tenta ler a configuração padrão
            from config_manager import ConfigManager
            selected_cfg = ConfigManager.read_config()

        if not selected_cfg:
            QMessageBox.critical(self, "Erro", "Nenhuma configuração de banco disponível.")
            return

        try:
            db_type = (selected_cfg.db_type or "").upper()

            # MSDE -> Windows Authentication (Trusted). Forçar ambos vazios.
            if db_type == 'MSDE':
                if username or password:
                    QMessageBox.information(
                        self,
                        "Autenticação Windows",
                        "Tipo de banco MSDE: será usado Windows Authentication (Trusted Connection).\n"
                        "Deixe Usuário e Senha vazios para usar a conta Windows atual."
                    )
                    return

                # Valida usando Trusted Connection (pede razão para mostrar mensagens apropriadas)
                user_data, reason = verify_user(None, None, selected_cfg, return_reason=True)

            else:
                # Para SQLSERVER (ou padrão), exige username+password (SQL Auth)
                if not username or not password:
                    QMessageBox.warning(
                        self,
                        "Credenciais necessárias",
                        "Preencha Usuário e Senha para autenticação SQL (TipoBanco=SQLSERVER)."
                    )
                    return

                user_data, reason = verify_user(username, password, selected_cfg, return_reason=True)

            if user_data:
                self.user_data = user_data
                self.selected_db = selected_cfg
                self.accept()
            else:
                # mostrar mensagem apropriada baseada na razão retornada
                if 'reason' in locals() and reason:
                    if reason == 'inactive':
                        QMessageBox.critical(
                            self,
                            "Sem Permissão",
                            "Usuário inativo. Contate o administrador para ativar a conta."
                        )
                    elif reason == 'insufficient_level':
                        QMessageBox.critical(
                            self,
                            "Sem Permissão",
                            "Acesso restrito: somente usuários com nível Supervisor podem acessar este módulo."
                        )
                    elif reason == 'invalid_credentials':
                        QMessageBox.critical(
                            self,
                            "Erro de Login",
                            "Usuário ou senha inválidos."
                        )
                    else:
                        QMessageBox.critical(
                            self,
                            "Erro de Login",
                            "Falha ao validar usuário. Contate o administrador."
                        )
                else:
                    QMessageBox.critical(
                        self,
                        "Erro de Login",
                        "Usuário ou senha inválidos."
                    )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro",
                f"Erro ao conectar/validar no banco selecionado:\n{str(e)}"
            )

    def test_connection(self):
        """Testa a conexão administrativa (SA ou Trusted) para o DB selecionado

        Exibe a mensagem de sucesso ou o erro ODBC completo para auxiliar debug.
        """
        # Seleciona DB escolhido primeiro
        selected_cfg = None
        if self.db_combo:
            idx = self.db_combo.currentIndex()
            selected_cfg = self.db_options[idx]
        else:
            from config_manager import ConfigManager
            selected_cfg = ConfigManager.read_config()

        if not selected_cfg:
            QMessageBox.critical(self, "Erro", "Nenhuma configuração de banco disponível para testar.")
            return

        try:
            # Usa get_db_connection que já aplica SA/Trusted conforme o tipo
            conn = get_db_connection(selected_cfg, None, None)
            try:
                cur = conn.cursor()
                # Small sanity query
                cur.execute("SELECT DB_NAME() AS BaseAtual")
                row = cur.fetchone()
                base = row[0] if row else "(desconhecida)"
                QMessageBox.information(self, "Conexão bem-sucedida", f"Conectado com sucesso à base: {base}")
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            # Mostra a mensagem completa do erro ODBC/pyodbc para diagnóstico
            err_msg = str(e)
            # Não tentamos automaticamente conectar com as credenciais informadas
            # quando TipoBanco=SQLSERVER — por regra do sistema, a conexão ao
            # servidor deve ser feita com SA/csloginciasoft; as credenciais
            # digitadas são apenas para autenticação no módulo.
            msg = (
                "Tentativa (SA/Trusted) falhou:\n" + err_msg +
                "\n\nObservação: por configuração, quando TipoBanco=SQLSERVER a aplicação sempre tenta\n"
                "conectar ao servidor usando UID=sa e PWD=csloginciasoft.\n"
                "O usuário/senha informados no formulário são utilizados apenas para validar o acesso\n"
                "ao módulo (consulta na tabela Usuarios) e não para estabelecer a conexão com o SQL Server.\n"
                "Se desejar tentar conectar com as credenciais informadas, use a ferramenta externa de\n"
                "teste ou habilite esse comportamento manualmente no código."
            )
            QMessageBox.critical(self, "Falha na conexão", msg)
        
def _format_iso_timestamp(ts: str) -> str:
    """Formata timestamps ISO removendo microsegundos quando possível.

    Exemplos:
      '2025-12-19T10:36:51.210698' -> '2025-12-19T10:36:51'
      se parsing falhar, remove parte após '.' como fallback.
    """
    if not ts:
        return ''
    try:
        # usa fromisoformat para aceitar offsets também
        dt = _dt.datetime.fromisoformat(ts)
        # retorna no formato 'YYYY-MM-DD HH:MM:SS' (espaço entre data e hora)
        return dt.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        # fallback simples: corta após ponto
        return ts.split('.')[0] if '.' in ts else ts

    

    def test_connection(self):
        """Testa a conexão administrativa (SA ou Trusted) para o DB selecionado

        Exibe a mensagem de sucesso ou o erro ODBC completo para auxiliar debug.
        """
        # Seleciona DB escolhido primeiro
        selected_cfg = None
        if self.db_combo:
            idx = self.db_combo.currentIndex()
            selected_cfg = self.db_options[idx]
        else:
            from config_manager import ConfigManager
            selected_cfg = ConfigManager.read_config()

        if not selected_cfg:
            QMessageBox.critical(self, "Erro", "Nenhuma configuração de banco disponível para testar.")
            return

        try:
            # Usa get_db_connection que já aplica SA/Trusted conforme o tipo
            conn = get_db_connection(selected_cfg, None, None)
            try:
                cur = conn.cursor()
                # Small sanity query
                cur.execute("SELECT DB_NAME() AS BaseAtual")
                row = cur.fetchone()
                base = row[0] if row else "(desconhecida)"
                QMessageBox.information(self, "Conexão bem-sucedida", f"Conectado com sucesso à base: {base}")
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            # Mostra a mensagem completa do erro ODBC/pyodbc para diagnóstico
            err_msg = str(e)
            # Não tentamos automaticamente conectar com as credenciais informadas
            # quando TipoBanco=SQLSERVER — por regra do sistema, a conexão ao
            # servidor deve ser feita com SA/csloginciasoft; as credenciais
            # digitadas são apenas para autenticação no módulo.
            msg = (
                "Tentativa (SA/Trusted) falhou:\n" + err_msg +
                "\n\nObservação: por configuração, quando TipoBanco=SQLSERVER a aplicação sempre tenta\n"
                "conectar ao servidor usando UID=sa e PWD=csloginciasoft.\n"
                "O usuário/senha informados no formulário são utilizados apenas para validar o acesso\n"
                "ao módulo (consulta na tabela Usuarios) e não para estabelecer a conexão com o SQL Server.\n"
                "Se desejar tentar conectar com as credenciais informadas, use a ferramenta externa de\n"
                "teste ou habilite esse comportamento manualmente no código."
            )
            QMessageBox.critical(self, "Falha na conexão", msg)

class QueryBuilderTab(QWidget):
    """Aba de construção de consultas"""
    
    query_executed = pyqtSignal(list, list)  # (columns, data)
    
    def __init__(self, query_builder: QueryBuilder, query_manager: QueryManager, session_logger: SessionLogger = None):
        super().__init__()
        self.qb = query_builder
        self.qm = query_manager
        self.session_logger = session_logger
        self.selected_tables = []
        self.selected_columns = []
        # Carrega mapeamento de nomes amigáveis (se houver)
        self._table_name_map = {}
        # cache de colunas por tabela (chave: 'schema.table') para reduzir consultas ao banco
        self._columns_cache = {}
        self.setup_ui()

    def _get_columns_cached(self, schema: str, table_name: str):
        """Retorna lista de ColumnInfo para a tabela, usando cache por sessão."""
        key = f"{schema}.{table_name}".lower()
        if key in self._columns_cache:
            return self._columns_cache[key]
        cols = self.qb.get_table_columns(schema, table_name)
        # armazena mesmo que lista vazia
        self._columns_cache[key] = cols
        return cols
    
    def setup_ui(self):
        layout = QHBoxLayout()
        
        # === PAINEL ESQUERDO: Seleção ===
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        # Tabelas disponíveis
        left_layout.addWidget(QLabel("<b>📂 De onde vêm os dados?</b>"))
        self.table_search = QLineEdit()
        self.table_search.setPlaceholderText("Pesquisar fontes...")
        self.table_search.textChanged.connect(self.filter_tables)
        # visual improvements: ícone de lupa e botão limpar
        icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'logo.ico')
        try:
            if os.path.exists(icon_path):
                self.table_search.addAction(QIcon(icon_path), QLineEdit.LeadingPosition)
            self.table_search.setClearButtonEnabled(True)
        except Exception:
            pass
        left_layout.addWidget(self.table_search)

        self.tables_list = QListWidget()
        self.tables_list.setSelectionMode(QListWidget.MultiSelection)
        # Menu de contexto para tabelas: permitir Mostrar dependências via botão direito
        self.tables_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tables_list.customContextMenuRequested.connect(self.on_tables_context_menu)
        left_layout.addWidget(self.tables_list)
        
        # Botão para adicionar tabelas
        btn_add_tables = QPushButton("➕ Adicionar fontes selecionadas")
        btn_add_tables.clicked.connect(self.add_selected_tables)
        left_layout.addWidget(btn_add_tables)
        
        left_panel.setLayout(left_layout)
        
        # === PAINEL CENTRAL: Tabelas e Colunas Selecionadas ===
        center_panel = QWidget()
        center_layout = QVBoxLayout()
        
        center_layout.addWidget(QLabel("<b>📌 Fontes de dados escolhidas</b>"))
        self.selected_tables_list = QListWidget()
        center_layout.addWidget(self.selected_tables_list)
        
        # Botões para gerenciar tabelas
        btn_layout = QHBoxLayout()
        btn_remove_table = QPushButton("➖ Remover fonte")
        btn_remove_table.clicked.connect(self.remove_selected_table)
        btn_layout.addWidget(btn_remove_table)
        
        btn_clear_tables = QPushButton("🧹 Limpar tudo")
        btn_clear_tables.clicked.connect(self.clear_selection)
        btn_layout.addWidget(btn_clear_tables)
        center_layout.addLayout(btn_layout)
        
        center_layout.addWidget(QLabel("<b>🧩 Informações disponíveis</b>"))
        # Busca rápida nas colunas disponíveis
        self.column_search = QLineEdit()
        self.column_search.setPlaceholderText("Pesquisar informações...")
        self.column_search.setClearButtonEnabled(True)
        self.column_search.textChanged.connect(self.filter_columns)
        center_layout.addWidget(self.column_search)

        self.columns_list = QListWidget()
        self.columns_list.setSelectionMode(QListWidget.MultiSelection)
        center_layout.addWidget(self.columns_list)
        # seleção rápida de colunas
        col_btns = QHBoxLayout()
        btn_select_all = QPushButton("✔️ Marcar todas")
        btn_select_all.clicked.connect(self.select_all_columns)
        col_btns.addWidget(btn_select_all)
        btn_deselect_all = QPushButton("✖️ Desmarcar todas")
        btn_deselect_all.clicked.connect(self.deselect_all_columns)
        col_btns.addWidget(btn_deselect_all)
        center_layout.addLayout(col_btns)

        btn_add_columns = QPushButton("➕ Adicionar informações")
        btn_add_columns.clicked.connect(self.add_selected_columns)
        center_layout.addWidget(btn_add_columns)
        
        center_panel.setLayout(center_layout)
        
        # === PAINEL DIREITO: Configurações e Execução ===
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        right_layout.addWidget(QLabel("<b>✅ Informações que aparecerão no relatório</b>"))
        self.selected_columns_list = QListWidget()
        right_layout.addWidget(self.selected_columns_list)
        
        btn_remove_column = QPushButton("➖ Remover informação")
        btn_remove_column.clicked.connect(self.remove_selected_column)
        right_layout.addWidget(btn_remove_column)

        # Tipo de JOIN
        right_layout.addWidget(QLabel("<b>🔗 Como os dados se relacionam</b>"))
        self.join_type_combo = QComboBox()
        self.join_type_combo.addItems(["INNER JOIN", "LEFT JOIN", "RIGHT JOIN"])
        right_layout.addWidget(self.join_type_combo)

        # Cláusula WHERE
        right_layout.addWidget(QLabel("<b>🎯 Filtros (opcional)</b>"))
        self.where_input = QTextEdit()
        self.where_input.setPlaceholderText("Ex: DataVenda >= '2024-01-01'")
        self.where_input.setMaximumHeight(100)
        right_layout.addWidget(self.where_input)

        # SQL Gerada
        right_layout.addWidget(QLabel("<b>🧠 Consulta criada automaticamente</b>"))
        self.sql_preview = QTextEdit()
        self.sql_preview.setReadOnly(True)
        self.sql_preview.setMaximumHeight(150)
        right_layout.addWidget(self.sql_preview)

        # Botões de ação
        action_layout = QVBoxLayout()
        # Opções de alias
        alias_layout = QHBoxLayout()
        self.use_alias_cb = QCheckBox("Exibir qual tipo de nome para a tabela na consulta:")
        self.use_alias_cb.setChecked(True)
        alias_layout.addWidget(self.use_alias_cb)

        self.alias_style_combo = QComboBox()
        self.alias_style_combo.addItems(["Curto (apg,cli)", "Descritivo (apagar,clientes)", "Nenhum (nomes qualificados)"])
        alias_layout.addWidget(self.alias_style_combo)
        action_layout.addLayout(alias_layout)

        btn_generate = QPushButton("🧩 Gerar consulta")
        btn_generate.clicked.connect(self.generate_sql)
        action_layout.addWidget(btn_generate)

        btn_execute = QPushButton("▶️ Executar consulta")
        btn_execute.clicked.connect(self.execute_query)
        btn_execute.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        action_layout.addWidget(btn_execute)

        btn_save = QPushButton("💾 Salvar consulta")
        btn_save.clicked.connect(self.save_query)
        action_layout.addWidget(btn_save)

        btn_load = QPushButton("📂 Carregar consulta")
        btn_load.clicked.connect(self.load_query)
        action_layout.addWidget(btn_load)

        btn_delete = QPushButton("🗑️ Excluir consulta")
        btn_delete.clicked.connect(self.delete_query)
        action_layout.addWidget(btn_delete)

        btn_manage = QPushButton("🔧 Gerenciar consultas")
        # Abrir o gerenciador de consultas da janela principal (MainWindow)
        btn_manage.clicked.connect(lambda: (self.window().open_manage_queries() if hasattr(self.window(), 'open_manage_queries') else None))
        action_layout.addWidget(btn_manage)
        
        right_layout.addLayout(action_layout)
        right_layout.addStretch()
        
        right_panel.setLayout(right_layout)
        
        # === SPLITTER PARA REDIMENSIONAMENTO ===
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 2)
        
        layout.addWidget(splitter)
        self.setLayout(layout)
        
        # Carrega tabelas
        # carrega mapeamento de nomes amigáveis (se não foi carregado antes)
        if not getattr(self, '_table_name_map', None):
            self._table_name_map = self._load_table_name_mapping()
        self.load_tables()
        # registra evento de abertura de construtor
        try:
            if getattr(self, 'session_logger', None):
                self.session_logger.log('open_query_builder', 'Acesso ao construtor de consultas')
        except Exception:
            pass
        # estado para tooltip persistente
        self._details_dialog = None
        self._last_hovered_table = None
        # Duplo clique: adiciona automaticamente
        self.tables_list.itemDoubleClicked.connect(lambda _ : self.add_selected_tables())
        # Single click on a table toggles its presence in selected_tables_list
        self.tables_list.itemClicked.connect(self.toggle_selected_table)
        self.columns_list.itemDoubleClicked.connect(lambda _ : self.add_selected_columns())
        # Menu de contexto na lista de colunas para inserir no WHERE
        self.columns_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.columns_list.customContextMenuRequested.connect(self.on_columns_context_menu)
        # Mostrar detalhes da tabela: removido comportamento de abrir no clique simples.
        # O popup agora abre apenas via menu de contexto (botão direito -> Mostrar dependências).
        # Clique em tabela selecionada mostra apenas suas colunas disponíveis
        self.selected_tables_list.itemClicked.connect(self.on_selected_table_clicked)
    
    def load_tables(self):
        """Carrega tabelas e views do banco"""
        try:
            tables = self.qb.get_tables_and_views()
            self.tables_list.clear()
            for table in tables:
                # mostra apenas o identificador técnico [schema].TableName — não exibe o sufixo de tipo (TABLE/VIEW)
                raw = f"[{table.schema}].{table.name}"
                # exibe nome amigável se existir — mostra ambos: "Amigável — [schema].Tabela (...)"
                key = f"{table.schema}.{table.name}"
                friendly = self._table_name_map.get(key)
                display = f"{friendly} — {raw}" if friendly else raw
                it = QListWidgetItem(display)
                # sempre preserve o texto técnico bruto no UserRole para construir SQL
                it.setData(Qt.UserRole, raw)
                self.tables_list.addItem(it)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao carregar tabelas:\n{str(e)}")

    def _load_table_name_mapping(self) -> dict:
        """Carrega mapeamento de nomes amigáveis de `table_friendly_names.json` se existir."""
        try:
            p = os.path.join(os.path.dirname(__file__), 'table_friendly_names.json')
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception as e:
            print(f"Falha ao carregar mapeamento de nomes amigáveis: {e}")
        return {}

    def _save_table_name_mapping(self):
        """Persiste o mapeamento de nomes amigáveis em arquivo JSON."""
        try:
            p = os.path.join(os.path.dirname(__file__), 'table_friendly_names.json')
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(self._table_name_map, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Falha ao salvar mapeamento de nomes amigáveis: {e}")

    def show_table_details(self, item):
        """Mostra diálogo modeless com PKs e dependências quando a tabela for clicada."""
        try:
            table_text = item.data(Qt.UserRole) or item.text()
            parts = table_text.split('.')
            schema = parts[0].strip('[]')
            table_name = parts[1].split('(')[0].strip()

            deps = self.qb.get_table_dependencies(schema, table_name)
            pk_cols = self.qb.get_primary_keys(schema, table_name)

            html = f"<b>{schema}.{table_name}</b><br>"
            if pk_cols:
                html += "<i>Primary Key:</i> " + ", ".join(pk_cols) + "<br><br>"

            if deps['references']:
                html += "<b>Referências (esta tabela -> outra):</b><br>"
                for r in deps['references']:
                    html += f"{r[1]}({r[2]}) -> {r[4]}({r[5]})<br>"
                html += "<br>"

            if deps['referenced_by']:
                html += "<b>Referenciado por (outras -> esta):</b><br>"
                for r in deps['referenced_by']:
                    html += f"{r[1]}({r[2]}) -> {r[4]}({r[5]})<br>"

            # create dialog if needed
            if self._details_dialog is None:
                self._details_dialog = QDialog(self, flags=Qt.Tool)
                # define window title to avoid default 'python' in the titlebar
                self._details_dialog.setWindowTitle("Dependências da tabela")
                self._details_dialog.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
                layout = QVBoxLayout(self._details_dialog)
                self._details_text = QTextEdit()
                self._details_text.setReadOnly(True)
                self._details_text.setLineWrapMode(QTextEdit.NoWrap)
                layout.addWidget(self._details_text)
                # add close button
                btns = QDialogButtonBox(QDialogButtonBox.Close)
                btns.rejected.connect(self._details_dialog.hide)
                btns.clicked.connect(lambda btn: self._details_dialog.hide())
                layout.addWidget(btns)
                self._details_dialog.setLayout(layout)
                self._details_dialog.setAttribute(Qt.WA_ShowWithoutActivating)
                self._details_dialog.setMinimumWidth(700)

            pre_html = f"<pre style='font-family:monospace'>{html}</pre>"
            self._details_text.setHtml(pre_html)
            self._details_dialog.adjustSize()
            try:
                doc_height = int(self._details_text.document().size().height())
                h = min(800, max(120, doc_height + 40))
                self._details_dialog.resize(self._details_dialog.width(), h)
            except Exception:
                pass

            # position near the clicked item
            rect = self.tables_list.visualItemRect(item)
            global_pos = self.tables_list.viewport().mapToGlobal(rect.topLeft())
            self._details_dialog.move(global_pos.x() + rect.width() + 10, global_pos.y())
            self._details_dialog.show()
        except Exception as e:
            print(f"Erro ao mostrar detalhes da tabela: {e}")
    
    def add_selected_tables(self):
        """Adiciona tabelas selecionadas"""
        selected_items = self.tables_list.selectedItems()
        if not selected_items:
            return
        
        # existing raw texts
        existing_raw = [self._get_selected_table_raw_text(self.selected_tables_list.item(i)) for i in range(self.selected_tables_list.count())]
        for item in selected_items:
            raw = item.data(Qt.UserRole) or item.text()
            if raw not in existing_raw:
                idx = self.selected_tables_list.count() + 1
                display = f"{idx}: {raw}"
                li = QListWidgetItem(display)
                li.setData(Qt.UserRole, raw)
                self.selected_tables_list.addItem(li)
                existing_raw.append(raw)
        # renumerar para garantir sequência correta
        self._renumber_selected_tables()
        
        # Atualiza colunas disponíveis
        self.update_available_columns()
    
    def remove_selected_table(self):
        """Remove tabela selecionada"""
        current_item = self.selected_tables_list.currentItem()
        if current_item:
            self.selected_tables_list.takeItem(
                self.selected_tables_list.row(current_item)
            )
            self.update_available_columns()
            self._renumber_selected_tables()
    
    def clear_selection(self):
        """Limpa toda a seleção"""
        self.selected_tables_list.clear()
        self.selected_columns_list.clear()
        self.columns_list.clear()
        self.sql_preview.clear()
        self.where_input.clear()
    
    def update_available_columns(self):
        """Atualiza lista de colunas disponíveis baseado nas tabelas selecionadas"""
        self.columns_list.clear()
        
        for i in range(self.selected_tables_list.count()):
            item = self.selected_tables_list.item(i)
            table_text = self._get_selected_table_raw_text(item)
            # Parse: [schema].table (TYPE)
            parts = table_text.split('.')
            schema = parts[0].strip('[]')
            table_name = parts[1].split('(')[0].strip()
            
            try:
                columns = self._get_columns_cached(schema, table_name)
                pk_cols = self.qb.get_primary_keys(schema, table_name)
                for col in columns:
                    col_text = f"{table_name}.{col.column_name} ({col.data_type})"
                    item = QListWidgetItem(col_text)
                    # Highlight PK columns
                    if col.column_name in pk_cols:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                        item.setForeground(QColor('blue'))
                        item.setToolTip('Chave primária')
                    self.columns_list.addItem(item)
            except Exception as e:
                print(f"Erro ao carregar colunas de {table_name}: {e}")


    def _compute_aliases_for_selected_tables(self) -> dict:
        """Cria um mapa (schema,table) -> alias usando a mesma heurística do QueryBuilder.
        Retorna um dict onde a chave é (schema, table) e o valor é o alias (string).
        """
        aliases = {}
        used_aliases = {}

        def make_alias_short(table_name: str) -> str:
            base = ''.join([c for c in table_name if c.isalnum()])[:3].lower() or 't'
            if base not in used_aliases:
                used_aliases[base] = 1
                return base
            else:
                used_aliases[base] += 1
                return f"{base}{used_aliases[base]}"

        def make_alias_desc(table_name: str) -> str:
            base = ''.join([c for c in table_name if c.isalnum()]).lower()[:30] or 't'
            if base not in used_aliases:
                used_aliases[base] = 1
                return base
            else:
                used_aliases[base] += 1
                return f"{base}{used_aliases[base]}"

        # decide maker based on combo
        style = self.alias_style_combo.currentText() if hasattr(self, 'alias_style_combo') else 'Curto (apg,cli)'
        maker = make_alias_short if style.lower().startswith('curto') else make_alias_desc

        for i in range(self.selected_tables_list.count()):
            t = self._get_selected_table_raw_text(self.selected_tables_list.item(i))
            parts = t.split('.')
            schema = parts[0].strip('[]')
            table_name = parts[1].split('(')[0].strip()
            aliases[(schema, table_name)] = maker(table_name)

        return aliases

    def _get_selected_table_raw_text(self, item: QListWidgetItem) -> str:
        """Retorna o texto 'raw' (sem prefixo numérico) de um item de selected_tables_list.
        Se o UserRole estiver preenchido, retorna-o; senão tenta remover um prefixo numérico no formato 'N: '.
        """
        if not item:
            return ''
        raw = item.data(Qt.UserRole)
        if raw:
            return raw
        text = item.text()
        # remove prefixo 'N: ' se existir
        import re
        m = re.match(r'^\s*(\d+)\s*[:\-\)]?\s*(.*)$', text)
        if m:
            return m.group(2)
        return text

    def _renumber_selected_tables(self):
        """Renumera os itens em selected_tables_list preservando os textos raw no UserRole."""
        for idx in range(self.selected_tables_list.count()):
            item = self.selected_tables_list.item(idx)
            raw = item.data(Qt.UserRole) or self._get_selected_table_raw_text(item)
            # tenta extrair chave schema.table para buscar nome amigável
            try:
                parts = raw.split('.')
                schema = parts[0].strip('[]')
                table_name = parts[1].split('(')[0].strip()
                key = f"{schema}.{table_name}"
            except Exception:
                key = None
            friendly = self._table_name_map.get(key) if key else None
            display_body = f"{friendly} — {raw}" if friendly else raw
            display = f"{idx+1}: {display_body}"
            item.setText(display)
            item.setData(Qt.UserRole, raw)

    def toggle_selected_table(self, item: QListWidgetItem):
        """Ao clicar numa tabela na lista principal, alterna sua presença em selected_tables_list."""
        try:
            # usar o valor bruto armazenado no UserRole quando disponível
            raw = item.data(Qt.UserRole) or item.text()
            # procura se já existe
            found_index = None
            for i in range(self.selected_tables_list.count()):
                if self._get_selected_table_raw_text(self.selected_tables_list.item(i)) == raw:
                    found_index = i
                    break
            if found_index is not None:
                # remove
                self.selected_tables_list.takeItem(found_index)
                self._renumber_selected_tables()
            else:
                # adiciona ao final
                idx = self.selected_tables_list.count() + 1
                # apresenta nome amigável se existir
                try:
                    parts = raw.split('.')
                    schema = parts[0].strip('[]')
                    table_name = parts[1].split('(')[0].strip()
                    key = f"{schema}.{table_name}"
                except Exception:
                    key = None
                friendly = self._table_name_map.get(key) if key else None
                display_body = f"{friendly} — {raw}" if friendly else raw
                display = f"{idx}: {display_body}"
                li = QListWidgetItem(display)
                li.setData(Qt.UserRole, raw)
                self.selected_tables_list.addItem(li)
            self.update_available_columns()
        except Exception as e:
            print(f"Erro ao alternar seleção de tabela: {e}")

    def filter_columns(self, text: str):
        """Filtra a lista de colunas disponíveis por nome (case-insensitive)."""
        try:
            q = (text or '').strip().lower()
            for i in range(self.columns_list.count()):
                it = self.columns_list.item(i)
                if not q:
                    it.setHidden(False)
                else:
                    it.setHidden(q not in it.text().lower())
        except Exception as e:
            print(f"Erro ao filtrar colunas: {e}")

    def filter_tables(self, text: str):
        """Filtra a lista de tabelas por nome/termo de busca."""
        try:
            term = (text or '').strip().lower()
            for i in range(self.tables_list.count()):
                item = self.tables_list.item(i)
                item.setHidden(False if not term else term not in item.text().lower())
        except Exception as e:
            print(f"Erro ao filtrar tabelas: {e}")

    def on_tables_context_menu(self, pos):
        """Context menu for the tables list. Shows 'Mostrar dependências' when right-clicking a selected table."""
        item = self.tables_list.itemAt(pos)
        if not item:
            return
        # only offer the action when the item is selected
        if not item.isSelected():
            return
        menu = QMenu(self)
        act = QAction("Mostrar dependências", self)
        act.triggered.connect(lambda: self.show_table_details(item))
        menu.addAction(act)
        # Edit friendly name
        act2 = QAction("Editar nome amigável", self)
        def do_edit():
            try:
                raw = item.data(Qt.UserRole) or item.text()
                # key used in mapping
                parts = raw.split('.')
                schema = parts[0].strip('[]')
                table_name = parts[1].split('(')[0].strip()
                key = f"{schema}.{table_name}"
                current = self._table_name_map.get(key, '')
                text, ok = QInputDialog.getText(self, 'Editar nome amigável', f'Nome amigável para {key}:', text=current)
                if ok:
                    val = text.strip() if text else ''
                    if val:
                        self._table_name_map[key] = val
                    elif key in self._table_name_map:
                        del self._table_name_map[key]
                    self._save_table_name_mapping()
                    # atualiza o item exibido: mostra "friendly — raw" quando houver
                    friendly_val = self._table_name_map.get(key)
                    display = f"{friendly_val} — {raw}" if friendly_val else raw
                    item.setText(display)
                    # atualizar selected_tables_list se houver referência
                    for i in range(self.selected_tables_list.count()):
                        it = self.selected_tables_list.item(i)
                        raw2 = self._get_selected_table_raw_text(it)
                        if raw2 == raw:
                            # mantém raw em UserRole, atualiza texto exibido com prefixo e friendly se houver
                            display_body = f"{friendly_val} — {raw}" if friendly_val else raw
                            it.setText(f"{i+1}: {display_body}")
            except Exception as e:
                print(f"Erro ao editar nome amigável: {e}")
        act2.triggered.connect(do_edit)
        menu.addAction(act2)
        menu.exec_(self.tables_list.mapToGlobal(pos))

    def normalize_date(self, value: str) -> str:
        """Normaliza uma string de data para m-d-YYYY.
        Tenta usar dateutil.parser.parse quando disponível para tratar diversos formatos e timezones.
        Mantém fallback para parsing manual se dateutil não estiver instalado.
        Lança ValueError se não conseguir parsear.
        """
        v = (value or '').strip()
        if not v:
            raise ValueError("Data vazia")

        # Primeiro: tentar usar dateutil (muito mais robusto)
        try:
            from dateutil import parser as dateparser
            dt = dateparser.parse(v, dayfirst=False)
            return f"{dt.month}-{dt.day}-{dt.year}"
        except Exception:
            # fallback para heurísticas anteriores
            pass

        # tentativas de formatos comuns (inclui horas)
        fmts = [
            '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y', '%m-%d-%Y',
            '%d.%m.%Y', '%Y/%m/%d', '%Y.%m.%d',
            '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M',
            '%m/%d/%Y %H:%M:%S', '%m/%d/%Y %H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%d %H:%M:%S%z', '%d-%m-%Y %H:%M:%S'
        ]
        for f in fmts:
            try:
                dt = datetime.datetime.strptime(v, f)
                return f"{dt.month}-{dt.day}-{dt.year}"
            except Exception:
                continue
        # try ISO with optional timezone (including 'Z')
        try:
            vv = v
            if vv.endswith('Z') or vv.endswith('z'):
                vv = vv[:-1] + '+00:00'
            dt = datetime.datetime.fromisoformat(vv)
            return f"{dt.month}-{dt.day}-{dt.year}"
        except Exception:
            pass
        # último recurso: tentar números separados por - ou /
        for sep in ('-', '/', '.'):
            parts = v.split(sep)
            if len(parts) == 3:
                # heurística: se primeiro > 31 assume ano-first
                try:
                    p0 = int(parts[0]); p1 = int(parts[1]); p2 = int(parts[2])
                    # detectar posição do ano
                    if p0 > 31:
                        year = p0; month = p1; day = p2
                    elif p2 > 31:
                        year = p2; month = p0; day = p1
                    else:
                        # fallback assume mm-sep-dd-sep-yyyy
                        month = p0; day = p1; year = p2
                    return f"{int(month)}-{int(day)}-{int(year)}"
                except Exception:
                    continue
        raise ValueError(f"Formato de data inválido: {value}")

    def select_all_columns(self):
        try:
            for i in range(self.columns_list.count()):
                item = self.columns_list.item(i)
                item.setSelected(True)
        except Exception as e:
            print(f"Erro ao selecionar todas colunas: {e}")

    def deselect_all_columns(self):
        try:
            for i in range(self.columns_list.count()):
                item = self.columns_list.item(i)
                item.setSelected(False)
        except Exception as e:
            print(f"Erro ao desmarcar todas colunas: {e}")

    def on_columns_context_menu(self, pos):
        """Mostra menu de contexto na lista de colunas e permite inserir a coluna no WHERE"""
        item = self.columns_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_add = QAction("Adicionar no WHERE", self)
        act_add.triggered.connect(lambda: self.add_column_to_where(item))
        menu.addAction(act_add)
        menu.exec_(self.columns_list.mapToGlobal(pos))

    def add_column_to_where(self, item):
        """Insere referência à coluna no campo WHERE (usa schema detectado ou dbo por default)."""
        try:
            text = item.text()
            # formato esperado: table.column (type)
            table_col = text.split('(')[0].strip()
            parts = table_col.split('.')
            if len(parts) == 2:
                table_name, col_name = parts[0].strip(), parts[1].strip()
            else:
                # fallback
                table_name = parts[0].strip()
                col_name = ''

            # tenta encontrar schema nas tabelas selecionadas (usa raw text sem prefixo)
            schema = 'dbo'
            for i in range(self.selected_tables_list.count()):
                titem = self.selected_tables_list.item(i)
                ttext = self._get_selected_table_raw_text(titem)
                tparts = ttext.split('.')
                t_schema = tparts[0].strip('[]')
                t_name = tparts[1].split('(')[0].strip()
                if t_name.lower() == table_name.lower():
                    schema = t_schema
                    break

            # busca tipo de dado da coluna para sugerir operador/format
            data_type = None
            try:
                cols = self._get_columns_cached(schema, table_name)
                for c in cols:
                    if c.column_name.lower() == col_name.lower():
                        data_type = (c.data_type or '').lower()
                        break
            except Exception:
                data_type = None

            # cria referência qualificada — usa alias se a opção estiver marcada
            use_alias = getattr(self, 'use_alias_cb', None) and self.use_alias_cb.isChecked()
            if use_alias and self.alias_style_combo.currentText().lower().startswith('nenhum'):
                # explicitamente 'Nenhum' selecionado -> não usar alias
                use_alias = False

            if use_alias:
                aliases = self._compute_aliases_for_selected_tables()
                alias = aliases.get((schema, table_name))
                if alias:
                    field_ref = f"{alias}.[{col_name}]"
                else:
                    # fallback para qualificado completo
                    field_ref = f"[{schema}].[{table_name}].[{col_name}]"
            else:
                field_ref = f"[{schema}].[{table_name}].[{col_name}]"

            # mini-diálogo para escolher operador/valor
            dlg = QDialog(self)
            dlg.setWindowTitle(f"Adicionar filtro - {table_name}.{col_name}")
            vlayout = QVBoxLayout(dlg)
            vlayout.addWidget(QLabel(f"Coluna: {field_ref}"))

            op_combo = QComboBox()
            # determina operadores possíveis e default por tipo
            text_ops = ["=", "LIKE", "IN", "IS NULL"]
            num_ops = ["=", "<>", ">", "<", ">=", "<=", "BETWEEN", "IS NULL"]
            date_ops = ["=", ">=", "<=", "BETWEEN", "IS NULL"]

            if data_type and any(t in data_type for t in ("char", "text", "varchar", "nchar", "nvarchar")):
                ops = text_ops
                default_op = "="
            elif data_type and any(t in data_type for t in ("date", "time", "datetime", "smalldatetime", "timestamp")):
                ops = date_ops
                default_op = ">="
            elif data_type and any(t in data_type for t in ("int", "bigint", "smallint", "tinyint", "decimal", "numeric", "float", "real", "money")):
                ops = num_ops
                default_op = "="
            else:
                # fallback to text
                ops = text_ops
                default_op = "="

            op_combo.addItems(ops)
            try:
                op_combo.setCurrentText(default_op)
            except Exception:
                pass
            vlayout.addWidget(QLabel("Operador:"))
            vlayout.addWidget(op_combo)

            # Valores: suporte para BETWEEN (duas entradas) e um preview
            val1_edit = QLineEdit()
            val1_edit.setPlaceholderText("Valor 1")
            val2_edit = QLineEdit()
            val2_edit.setPlaceholderText("Valor 2 (usado em BETWEEN)")
            val2_edit.setVisible(False)

            vlayout.addWidget(QLabel("Valor 1:"))
            vlayout.addWidget(val1_edit)
            vlayout.addWidget(QLabel("Valor 2:"))
            vlayout.addWidget(val2_edit)

            # AND/OR selector (para quando já houver filtros existentes)
            connector_combo = QComboBox()
            connector_combo.addItems(["AND", "OR"])
            vlayout.addWidget(QLabel("Conector (se houver filtros existentes):"))
            vlayout.addWidget(connector_combo)

            # Preview da expressão
            preview_label = QLabel("")
            preview_label.setWordWrap(True)
            font = preview_label.font()
            font.setFamily('Courier')
            preview_label.setFont(font)
            vlayout.addWidget(QLabel("Pré-visualização:"))
            vlayout.addWidget(preview_label)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            vlayout.addWidget(buttons)
            # validação personalizada antes de aceitar
            def try_accept():
                op = op_combo.currentText()
                v1 = val1_edit.text().strip()
                v2 = val2_edit.text().strip()
                needs_text = data_type and any(t in data_type for t in ("char", "text", "varchar", "nchar", "nvarchar"))
                needs_date = data_type and any(t in data_type for t in ("date", "time", "datetime", "smalldatetime", "timestamp"))
                needs_number = data_type and any(t in data_type for t in ("int", "bigint", "smallint", "tinyint", "decimal", "numeric", "float", "real", "money"))

                # validações básicas de presença
                if op == "BETWEEN":
                    if not v1 or not v2:
                        QMessageBox.warning(dlg, "Valor ausente", "Para BETWEEN é necessário informar os dois valores.")
                        return
                elif op in ("IN",):
                    if not v1:
                        QMessageBox.warning(dlg, "Valor ausente", "Para IN informe pelo menos um valor separado por vírgula.")
                        return
                elif op != "IS NULL":
                    if not v1:
                        QMessageBox.warning(dlg, "Valor ausente", "Informe um valor para o filtro.")
                        return

                # validação estrita por tipo
                try:
                    if needs_number:
                        def check_num(s):
                            float(s)
                        if op == "BETWEEN":
                            check_num(v1); check_num(v2)
                        elif op == "IN":
                            parts = [p.strip() for p in v1.split(',') if p.strip()]
                            if not parts:
                                raise ValueError("Nenhum valor em IN")
                            for p in parts:
                                check_num(p)
                        elif op != "IS NULL":
                            check_num(v1)
                    if needs_date:
                        # tenta normalizar datas; normalize_date lança ValueError se inválida
                        if op == "BETWEEN":
                            self.normalize_date(v1); self.normalize_date(v2)
                        elif op == "IN":
                            parts = [p.strip() for p in v1.split(',') if p.strip()]
                            if not parts:
                                raise ValueError("Nenhum valor em IN")
                            for p in parts:
                                self.normalize_date(p)
                        elif op != "IS NULL":
                            self.normalize_date(v1)
                except ValueError as ve:
                    QMessageBox.warning(dlg, "Valor inválido", f"Falha na validação de tipo: {ve}")
                    return

                # tudo ok
                dlg.accept()

            buttons.accepted.connect(try_accept)
            buttons.rejected.connect(dlg.reject)

            # Atualiza visibilidade do val2 e preview conforme seleção
            def update_ui():
                op = op_combo.currentText()
                if op == "BETWEEN":
                    val2_edit.setVisible(True)
                else:
                    val2_edit.setVisible(False)
                # monta preview
                op = op_combo.currentText()
                v1 = val1_edit.text().strip()
                v2 = val2_edit.text().strip()
                needs_quotes = data_type and any(t in data_type for t in ("char", "text", "varchar", "nchar", "nvarchar"))
                needs_number = data_type and any(t in data_type for t in ("int", "bigint", "smallint", "tinyint", "decimal", "numeric", "float", "real", "money"))
                # helper para formatar números sem trailing .0 quando possível
                def format_number_str(s: str) -> str:
                    try:
                        f = float(s)
                        if f.is_integer():
                            return str(int(f))
                        return str(f)
                    except Exception:
                        return s
                if op == "IS NULL":
                    p = f"{field_ref} IS NULL"
                elif op == "IN":
                    parts = [p.strip() for p in v1.split(',') if p.strip()] if v1 else []
                    if needs_quotes:
                        parts = [f"'{p}'" for p in parts]
                    # if date, try to normalize for preview
                    if data_type and any(t in data_type for t in ("date", "time", "datetime", "smalldatetime", "timestamp")):
                        norm_parts = []
                        for p_val in parts:
                            # remove surrounding quotes if present
                            raw = p_val.strip("'")
                            try:
                                nd = self.normalize_date(raw)
                                norm_parts.append(f"'{nd}'")
                            except Exception:
                                norm_parts.append(p_val)
                        parts = norm_parts
                    elif data_type and any(t in data_type for t in ("int", "bigint", "smallint", "tinyint", "decimal", "numeric", "float", "real", "money")):
                        # numeric IN preview: format numbers
                        parts = [format_number_str(p) for p in parts]
                    p = f"{field_ref} IN ({', '.join(parts)})" if parts else f"{field_ref} IN (...)"
                elif op == "BETWEEN":
                    if v1 and v2:
                        if data_type and any(t in data_type for t in ("date", "time", "datetime", "smalldatetime", "timestamp")):
                            try:
                                a_val = f"'{self.normalize_date(v1)}'"
                            except Exception:
                                a_val = f"'{v1}'"
                            try:
                                b_val = f"'{self.normalize_date(v2)}'"
                            except Exception:
                                b_val = f"'{v2}'"
                        else:
                            if needs_number:
                                a_val = format_number_str(v1)
                                b_val = format_number_str(v2)
                            else:
                                a_val = f"'{v1}'" if needs_quotes else v1
                                b_val = f"'{v2}'" if needs_quotes else v2
                        p = f"{field_ref} BETWEEN {a_val} AND {b_val}"
                    else:
                        p = f"{field_ref} BETWEEN ... AND ..."
                else:
                    if v1:
                        if data_type and any(t in data_type for t in ("date", "time", "datetime", "smalldatetime", "timestamp")):
                            try:
                                v_norm = self.normalize_date(v1)
                                v = f"'{v_norm}'"
                            except Exception:
                                v = f"'{v1}'" if needs_quotes else v1
                        else:
                            if needs_number:
                                v = format_number_str(v1)
                            else:
                                v = f"'{v1}'" if needs_quotes else v1
                        p = f"{field_ref} {op} {v}"
                    else:
                        p = f"{field_ref} {op} ..."
                preview_label.setText(p)

            op_combo.currentTextChanged.connect(lambda _ : update_ui())
            val1_edit.textChanged.connect(lambda _ : update_ui())
            val2_edit.textChanged.connect(lambda _ : update_ui())
            # inicializa UI
            update_ui()

            if dlg.exec_() == QDialog.Accepted:
                op = op_combo.currentText()
                v1 = val1_edit.text().strip()
                v2 = val2_edit.text().strip()
                # monta expressão conforme operador e valores selecionados
                needs_text = data_type and any(t in data_type for t in ("char", "text", "varchar", "nchar", "nvarchar"))
                needs_date = data_type and any(t in data_type for t in ("date", "time", "datetime", "smalldatetime", "timestamp"))
                needs_number = data_type and any(t in data_type for t in ("int", "bigint", "smallint", "tinyint", "decimal", "numeric", "float", "real", "money"))

                if op == "IS NULL":
                    expr = f"{field_ref} IS NULL"
                elif op == "IN":
                    parts = [p.strip() for p in v1.split(',') if p.strip()]
                    if needs_date:
                        parts = [f"'{self.normalize_date(p)}'" for p in parts]
                    elif needs_text:
                        parts = [f"'{p}'" for p in parts]
                    else:
                        # numbers: format to remove trailing .0 when integer
                        if needs_number:
                            def format_number_str2(s: str) -> str:
                                try:
                                    f = float(s)
                                    if f.is_integer():
                                        return str(int(f))
                                    return str(f)
                                except Exception:
                                    return s
                            parts = [format_number_str2(p) for p in parts]
                        # else left as-is
                    expr = f"{field_ref} IN ({', '.join(parts)})"
                elif op == "BETWEEN":
                    if needs_date:
                        a = f"'{self.normalize_date(v1)}'"
                        b = f"'{self.normalize_date(v2)}'"
                    elif needs_number:
                        def format_number_str2(s: str) -> str:
                            try:
                                f = float(s)
                                if f.is_integer():
                                    return str(int(f))
                                return str(f)
                            except Exception:
                                return s
                        a = format_number_str2(v1)
                        b = format_number_str2(v2)
                    elif needs_text:
                        a = f"'{v1}'"; b = f"'{v2}'"
                    else:
                        a = f"'{v1}'"; b = f"'{v2}'"
                    expr = f"{field_ref} BETWEEN {a} AND {b}"
                else:
                    if needs_date:
                        v = f"'{self.normalize_date(v1)}'"
                    elif needs_number:
                        def format_number_str2(s: str) -> str:
                            try:
                                f = float(s)
                                if f.is_integer():
                                    return str(int(f))
                                return str(f)
                            except Exception:
                                return s
                        v = format_number_str2(v1)
                    elif needs_text:
                        v = f"'{v1}'"
                    else:
                        v = f"'{v1}'"
                    expr = f"{field_ref} {op} {v}"

                # insere no where_input usando conector selecionado
                connector = connector_combo.currentText()
                # append the new expression at the end (safer than inserting at cursor)
                current = self.where_input.toPlainText().strip()
                if not current:
                    # first expression: insert as-is
                    self.where_input.setPlainText(expr)
                else:
                    # if existing text already ends with a connector (AND/OR), don't add another
                    import re
                    if re.search(r"\b(and|or)\s*$", current, re.IGNORECASE):
                        new_text = current + ' ' + expr
                    else:
                        new_text = current + f' {connector} ' + expr
                    self.where_input.setPlainText(new_text)
                self.where_input.setFocus()
            else:
                # cancelado
                return
        except Exception as e:
            print(f"Erro ao adicionar coluna no WHERE: {e}")

    def eventFilter(self, source, event):
        # Mostrar tooltip com dependências ao mover o mouse sobre a lista de tabelas
        if source is self.tables_list.viewport() and event.type() == QEvent.MouseMove:
            pos = event.pos()
            item = self.tables_list.itemAt(pos)
            if item:
                try:
                    table_text = item.text()
                    parts = table_text.split('.')
                    schema = parts[0].strip('[]')
                    table_name = parts[1].split('(')[0].strip()
                    deps = self.qb.get_table_dependencies(schema, table_name)
                    pk_cols = self.qb.get_primary_keys(schema, table_name)

                    html = f"<b>{schema}.{table_name}</b><br>"
                    if pk_cols:
                        html += "<i>Primary Key:</i> " + ", ".join(pk_cols) + "<br><br>"

                    if deps['references']:
                        html += "<b>Referências (esta tabela -> outra):</b><br>"
                        for r in deps['references']:
                            html += f"{r[1]}({r[2]}) -> {r[4]}({r[5]})<br>"
                        html += "<br>"

                    if deps['referenced_by']:
                        html += "<b>Referenciado por (outras -> esta):</b><br>"
                        for r in deps['referenced_by']:
                            html += f"{r[1]}({r[2]}) -> {r[4]}({r[5]})<br>"

                    # show a modeless details dialog near the cursor
                    try:
                        if self._details_dialog is None:
                            self._details_dialog = QDialog(self, flags=Qt.Tool)
                            self._details_dialog.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
                            self._details_layout = QVBoxLayout(self._details_dialog)
                            self._details_text = QTextEdit()
                            self._details_text.setReadOnly(True)
                            # Don't wrap lines so correspondences remain on one line; show horizontal scrollbar
                            self._details_text.setLineWrapMode(QTextEdit.NoWrap)
                            self._details_layout.addWidget(self._details_text)
                            self._details_dialog.setLayout(self._details_layout)
                            # don't steal focus
                            self._details_dialog.setAttribute(Qt.WA_ShowWithoutActivating)
                            # make dialog wider by default to reduce wrapping
                            self._details_dialog.setMinimumWidth(700)

                        # update content only if changed table
                        if (schema, table_name) != self._last_hovered_table:
                            # use preformatted block to keep correspondence on same line
                            pre_html = f"<pre style='font-family:monospace'>{html}</pre>"
                            self._details_text.setHtml(pre_html)
                            # adjust size: increase height to fit content up to a max
                            self._details_dialog.adjustSize()
                            # calculate document height to set a reasonable dialog height
                            try:
                                doc_height = int(self._details_text.document().size().height())
                                # add padding
                                h = min(800, max(120, doc_height + 40))
                                self._details_dialog.resize(self._details_dialog.width(), h)
                            except Exception:
                                pass
                            global_pos = self.tables_list.viewport().mapToGlobal(pos)
                            self._details_dialog.move(global_pos.x() + 15, global_pos.y() + 15)
                            self._details_dialog.show()
                            self._last_hovered_table = (schema, table_name)
                    except Exception:
                        QToolTip.showText(self.tables_list.viewport().mapToGlobal(pos), html)
                except Exception:
                    # hide any persistent dialog on error
                    if getattr(self, '_details_dialog', None):
                        try:
                            self._details_dialog.hide()
                        except Exception:
                            pass
                        self._last_hovered_table = None
                    QToolTip.hideText()
            else:
                # hide persistent dialog when leaving the item
                if getattr(self, '_details_dialog', None):
                    try:
                        self._details_dialog.hide()
                    except Exception:
                        pass
                    self._last_hovered_table = None
                QToolTip.hideText()
            return True
        return super().eventFilter(source, event)

    def on_selected_table_clicked(self, item):
        """Quando o usuário clica numa tabela já selecionada, mostra apenas as colunas dessa tabela."""
        try:
            table_text = self._get_selected_table_raw_text(item)
            parts = table_text.split('.')
            schema = parts[0].strip('[]')
            table_name = parts[1].split('(')[0].strip()

            # Limpa colunas disponíveis e carrega apenas desta tabela
            self.columns_list.clear()
            columns = self._get_columns_cached(schema, table_name)
            for col in columns:
                col_text = f"{table_name}.{col.column_name} ({col.data_type})"
                self.columns_list.addItem(col_text)
        except Exception as e:
            print(f"Erro ao carregar colunas da tabela clicada: {e}")

    def add_selected_columns(self):
        """Adiciona colunas selecionadas"""
        selected_items = self.columns_list.selectedItems()
        if not selected_items:
            return
        
        for item in selected_items:
            if item.text() not in [self.selected_columns_list.item(i).text() 
                                  for i in range(self.selected_columns_list.count())]:
                self.selected_columns_list.addItem(item.text())
    
    def remove_selected_column(self):
        """Remove coluna selecionada"""
        current_item = self.selected_columns_list.currentItem()
        if current_item:
            self.selected_columns_list.takeItem(
                self.selected_columns_list.row(current_item)
            )
    
    def generate_sql(self):
        """Gera a SQL baseada na seleção"""
        try:
            # Valida seleção
            if self.selected_tables_list.count() == 0:
                QMessageBox.warning(self, "Aviso", "Selecione ao menos uma tabela")
                return
            
            if self.selected_columns_list.count() == 0:
                QMessageBox.warning(self, "Aviso", "Selecione ao menos uma coluna")
                return
            
            # Extrai tabelas
            tables = []
            for i in range(self.selected_tables_list.count()):
                table_text = self._get_selected_table_raw_text(self.selected_tables_list.item(i))
                parts = table_text.split('.')
                schema = parts[0].strip('[]')
                table_name = parts[1].split('(')[0].strip()
                tables.append((schema, table_name))
            
            # Extrai colunas
            columns = []
            for i in range(self.selected_columns_list.count()):
                col_text = self.selected_columns_list.item(i).text()
                # Parse: table.column (type)
                table_col = col_text.split('(')[0].strip()
                table_name, col_name = table_col.split('.')
                # Assume schema dbo por padrão
                columns.append(('dbo', table_name.strip(), col_name.strip()))
            
            # Tipo de JOIN
            join_type_text = self.join_type_combo.currentText()
            if "INNER" in join_type_text:
                join_type = JoinType.INNER
            elif "LEFT" in join_type_text:
                join_type = JoinType.LEFT
            else:
                join_type = JoinType.RIGHT
            
            # WHERE clause (somente passar se houver filtros)
            where_clause = self.where_input.toPlainText().strip()
            if not where_clause:
                where_clause = None

            # Determina modo de alias
            if not getattr(self, 'use_alias_cb', None) or not self.use_alias_cb.isChecked():
                alias_mode = 'none'
            else:
                idx = self.alias_style_combo.currentIndex() if getattr(self, 'alias_style_combo', None) else 0
                if idx == 0:
                    alias_mode = 'short'
                else:
                    alias_mode = 'descriptive' if idx == 1 else 'none'

            # Antes de gerar a SQL, normalize referências no WHERE:
            # - Se o WHERE usar aliases gerados anteriormente (ou diferentes estilos), substitui por forma totalmente qualificada
            #   [schema].[table].[col] para que o QueryBuilder possa aplicar os aliases atuais.
            # - Também converte ocorrências do tipo Table.Column (sem schema) para [schema].[table].[col].
            wc = where_clause
            if wc:
                try:
                    import re
                    # para cada tabela selecionada, tente detectar e substituir alias ou table.col
                    for (schema, table_name) in tables:
                        # aliases possíveis (mesma heurística que usamos para criar aliases)
                        def make_alias_short_local(name: str) -> str:
                            base = ''.join([c for c in name if c.isalnum()])[:3].lower() or 't'
                            return base
                        def make_alias_desc_local(name: str) -> str:
                            base = ''.join([c for c in name if c.isalnum()]).lower()[:30] or 't'
                            return base

                        short_alias = make_alias_short_local(table_name)
                        desc_alias = make_alias_desc_local(table_name)

                        # substitui alias.[col] ou alias.col  -> [schema].[table].[col]
                        for a in (short_alias, desc_alias):
                            # pattern cobre [alias].[col], alias.[col], alias.col, alias.[col name with spaces]
                            pat = re.compile(rf"\b{re.escape(a)}\.(?:\[([^\]]+)\]|([A-Za-z0-9_]+))")
                            def repl(m):
                                col = m.group(1) or m.group(2)
                                return f"[{schema}].[{table_name}].[{col}]"
                            wc = pat.sub(repl, wc)

                        # substituir Table.Col (sem schema) também
                        pat2 = re.compile(rf"\b{re.escape(table_name)}\.(?:\[([^\]]+)\]|([A-Za-z0-9_]+))")
                        def repl2(m):
                            col = m.group(1) or m.group(2)
                            return f"[{schema}].[{table_name}].[{col}]"
                        wc = pat2.sub(repl2, wc)
                except Exception:
                    # se falhar na normalização, continue com where original
                    wc = where_clause

            # Gera SQL
            # safety: remove accidental leading connectors (AND/OR) to avoid 'WHERE AND ...'
            try:
                import re
                if wc:
                    wc = re.sub(r"^\s*(and|or)\b\s*", "", wc, flags=re.IGNORECASE)
            except Exception:
                pass

            sql = self.qb.build_query(tables, columns, None, wc, alias_mode=alias_mode)
            # Se não houver filtros, exibe comentário informativo APÓS a consulta no preview
            if not where_clause:
                preview = sql + "\n-- Sem filtros aplicados"
            else:
                preview = sql
            self.sql_preview.setPlainText(preview)
            try:
                if getattr(self, 'session_logger', None):
                    self.session_logger.log('generate_sql', 'Gerou preview de SQL', {'preview': preview[:200]})
            except Exception:
                pass
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao gerar SQL:\n{str(e)}")
    
    def execute_query(self):
        """Executa a consulta"""
        sql = self.sql_preview.toPlainText().strip()
        
        if not sql:
            QMessageBox.warning(self, "Aviso", "Gere a SQL primeiro")
            return
        # Valida SQL
        # Se não houver WHERE, permitir execução quando as tabelas selecionadas
        # não contiverem colunas impeditivas (lista em excecao.py).
        where_present = bool(re.search(r"\bwhere\b", sql.lower()))
        need_where = False
        if not where_present:
            try:
                tables = []
                for i in range(self.selected_tables_list.count()):
                    table_text = self._get_selected_table_raw_text(self.selected_tables_list.item(i))
                    parts = table_text.split('.')
                    schema = parts[0].strip('[]')
                    table_name = parts[1].split('(')[0].strip()
                    tables.append((schema, table_name))

                for schema, table_name in tables:
                    try:
                        cols = self._get_columns_cached(schema, table_name)
                        for c in cols:
                            if (c.column_name or '').lower() in set([c.lower() for c in IMPEDING_COLUMNS]):
                                need_where = True
                                break
                        if need_where:
                            break
                    except Exception:
                        need_where = True
                        break
            except Exception:
                need_where = True

        is_valid, error_msg = validar_sql(sql)
        # Allow omission of WHERE when validation failed only due to missing WHERE AND we determined
        # via metadata that WHERE isn't required for these tables.
        if not is_valid:
            if error_msg.strip().lower() == 'falta cláusula where' and not need_where:
                is_valid = True
            else:
                QMessageBox.critical(
                    self,
                    "SQL Inválida",
                    f"A consulta não passou na validação de segurança:\n\n{error_msg}"
                )
                return
        
        try:
            if getattr(self, 'session_logger', None):
                self.session_logger.log('execute_query_attempt', 'Tentativa de execução', {'sql_preview': sql[:200]})
            columns, data = self.qb.execute_query(sql)
            try:
                if getattr(self, 'session_logger', None):
                    self.session_logger.log('execute_query_success', f'Retorno {len(data)} registros', {'rows': len(data)})
            except Exception:
                pass
            self.query_executed.emit(columns, data)
            QMessageBox.information(
                self,
                "Sucesso",
                f"Consulta executada com sucesso!\n{len(data)} registros retornados."
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao executar consulta:\n{str(e)}")
    
    def save_query(self):
        """Salva a consulta atual"""
        sql = self.sql_preview.toPlainText().strip()
        if not sql:
            QMessageBox.warning(self, "Aviso", "Gere a SQL primeiro")
            return
        # Decide se é necessário exigir WHERE para salvar
        where_present = bool(re.search(r"\bwhere\b", sql.lower()))
        need_where = False
        if not where_present:
            # Se não houver WHERE, verifica se alguma das tabelas selecionadas
            # tem colunas 'impeditivas' (datas ou codempresa). Se sim, exigimos WHERE.
            # lista de colunas que tornam obrigatório o filtro WHERE (definida em excecao.py)
            impeding = set([c.lower() for c in IMPEDING_COLUMNS])
            try:
                # coletar tabelas selecionadas
                tables = []
                for i in range(self.selected_tables_list.count()):
                    table_text = self._get_selected_table_raw_text(self.selected_tables_list.item(i))
                    parts = table_text.split('.')
                    schema = parts[0].strip('[]')
                    table_name = parts[1].split('(')[0].strip()
                    tables.append((schema, table_name))

                for schema, table_name in tables:
                    try:
                        cols = self.qb.get_table_columns(schema, table_name)
                        for c in cols:
                            if (c.column_name or '').lower() in impeding:
                                need_where = True
                                break
                        if need_where:
                            break
                    except Exception:
                        # se não conseguir ler colunas do banco, seja conservador e exija WHERE
                        need_where = True
                        break
            except Exception:
                need_where = True

        # Se houver WHERE ou se determinamos que é necessário, valide a SQL normalmente
        if where_present or need_where:
            is_valid, error_msg = validar_sql_for_save(sql)
            if not is_valid:
                QMessageBox.critical(
                    self,
                    "SQL Inválida",
                    f"Não é possível salvar esta consulta:\n\n{error_msg}"
                )
                return
        
        # Solicita nome
        name, ok = QInputDialog.getText(
            self,
            "Salvar Consulta",
            "Nome da consulta:",
            QLineEdit.Normal
        )
        
        if not ok or not name:
            return
        
        # Solicita descrição
        description, ok = QInputDialog.getText(
            self,
            "Salvar Consulta",
            "Descrição (opcional):",
            QLineEdit.Normal
        )
        
        if not ok:
            return
        
        try:
            # Verifica se já existe
            existing = self.qm.get_query(name)
            if existing:
                reply = QMessageBox.question(
                    self,
                    "Consulta Existente",
                    f"Já existe uma consulta com o nome '{name}'.\nDeseja sobrescrevê-la?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
            
            # Salva
            self.qm.add_query(
                name=name,
                sql=sql,
                description=description,
                created_by="Usuario",  # Pode passar o usuário logado
                overwrite=(existing is not None)
            )
            try:
                if getattr(self, 'session_logger', None):
                    self.session_logger.log('save_query', f"Salvou consulta '{name}'", {'name': name})
            except Exception:
                pass
            QMessageBox.information(self, "Sucesso", "Consulta salva com sucesso!")
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar consulta:\n{str(e)}")
    
    def load_query(self):
        """Carrega uma consulta salva"""
        queries = self.qm.list_queries()
        
        if not queries:
            QMessageBox.information(self, "Informação", "Nenhuma consulta salva encontrada")
            return
        
        # Mostra lista de consultas
        query_names = [q.name for q in queries]
        name, ok = QInputDialog.getItem(
            self,
            "Carregar Consulta",
            "Selecione a consulta:",
            query_names,
            0,
            False
        )
        
        if not ok or not name:
            return
        
        query = self.qm.get_query(name)
        if query:
            self.sql_preview.setPlainText(query.sql)
            try:
                if getattr(self, 'session_logger', None):
                    self.session_logger.log('load_query', f"Carregou consulta '{query.name}'", {'name': query.name})
            except Exception:
                pass
            QMessageBox.information(
                self,
                "Consulta Carregada",
                    f"Nome: {query.name}\n"
                    f"Descrição: {query.description}\n"
                    f"Criada: {_format_iso_timestamp(query.created_at)}"
            )

    def delete_query(self):
        """Exclui uma consulta (prompt simples) via QueryBuilderTab."""
        queries = self.qm.list_queries()
        if not queries:
            QMessageBox.information(self, "Informação", "Nenhuma consulta salva encontrada")
            return

        query_names = [q.name for q in queries]
        name, ok = QInputDialog.getItem(
            self,
            "Excluir Consulta",
            "Selecione a consulta a excluir:",
            query_names,
            0,
            False
        )

        if not ok or not name:
            return

        reply = QMessageBox.question(
            self,
            "Confirmação",
            f"Tem certeza que deseja excluir a consulta '{name}'? Esta ação não pode ser desfeita.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        try:
            ok = self.qm.delete_query(name)
            if ok:
                try:
                    if getattr(self, 'session_logger', None):
                        self.session_logger.log('delete_query', f"Excluiu consulta '{name}'", {'name': name})
                except Exception:
                    pass
                QMessageBox.information(self, "Sucesso", f"Consulta '{name}' excluída com sucesso.")
            else:
                QMessageBox.warning(self, "Falha", f"Não foi possível excluir a consulta '{name}'.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao excluir consulta:\n{str(e)}")


class ManageQueriesDialog(QDialog):
    """Diálogo para gerenciar consultas salvas: listar, renomear, exportar e excluir múltiplas."""

    def __init__(self, parent, query_manager: QueryManager):
        super().__init__(parent)
        self.qm = query_manager
        self.setWindowTitle("Gerenciar consultas")
        self.setMinimumSize(700, 400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Lista com seleção múltipla
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(self.list_widget)

        # Informações laterais
        btn_layout = QHBoxLayout()
        self.btn_rename = QPushButton("Renomear")
        self.btn_rename.clicked.connect(self.rename_selected)
        btn_layout.addWidget(self.btn_rename)

        self.btn_export = QPushButton("Exportar (.sql)")
        self.btn_export.clicked.connect(self.export_selected)
        btn_layout.addWidget(self.btn_export)

        self.btn_delete = QPushButton("Excluir selecionadas")
        self.btn_delete.clicked.connect(self.delete_selected)
        btn_layout.addWidget(self.btn_delete)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.clicked.connect(self.load_queries)
        btn_layout.addWidget(self.btn_refresh)

        btn_layout.addStretch()

        self.btn_close = QPushButton("Fechar")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        self.load_queries()

    def load_queries(self):
        self.list_widget.clear()
        try:
            queries = self.qm.list_queries()
            for q in queries:
                # exibe nome e data (para contexto) — formata timestamp sem microssegundos
                mod = _format_iso_timestamp(q.modified_at)
                item = QListWidgetItem(f"{q.name} — {mod} — {q.description}")
                item.setData(Qt.UserRole, q.name)
                self.list_widget.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao carregar consultas:\n{e}")

    def rename_selected(self):
        sel = self.list_widget.selectedItems()
        if not sel:
            QMessageBox.information(self, "Informação", "Selecione ao menos uma consulta para renomear (1).")
            return
        if len(sel) > 1:
            QMessageBox.information(self, "Informação", "Selecione apenas uma consulta para renomear.")
            return
        name = sel[0].data(Qt.UserRole)
        new_name, ok = QInputDialog.getText(self, "Renomear consulta", f"Novo nome para '{name}':")
        if not ok or not new_name:
            return
        try:
            self.qm.rename_query(name, new_name)
            QMessageBox.information(self, "Sucesso", f"Consulta renomeada para '{new_name}'.")
            self.load_queries()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao renomear: {e}")

    def export_selected(self):
        sel = self.list_widget.selectedItems()
        if not sel:
            QMessageBox.information(self, "Informação", "Selecione uma ou mais consultas para exportar.")
            return
        for item in sel:
            name = item.data(Qt.UserRole)
            q = self.qm.get_query(name)
            if not q:
                continue
            default_name = f"{name}.sql"
            path, _ = QFileDialog.getSaveFileName(self, f"Exportar '{name}' como...", default_name, "SQL Files (*.sql);;All Files (*)")
            if path:
                try:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(q.sql)
                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Falha ao exportar '{name}': {e}")

    def delete_selected(self):
        sel = self.list_widget.selectedItems()
        if not sel:
            QMessageBox.information(self, "Informação", "Selecione ao menos uma consulta para excluir.")
            return
        names = [it.data(Qt.UserRole) for it in sel]
        reply = QMessageBox.question(self, "Confirmação", f"Excluir {len(names)} consulta(s)?\n" + "\n".join(names), QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No:
            return
        failed = []
        for n in names:
            try:
                ok = self.qm.delete_query(n)
                if not ok:
                    failed.append(n)
            except Exception:
                failed.append(n)
        if failed:
            QMessageBox.warning(self, "Aviso", f"Falha ao excluir: {', '.join(failed)}")
        else:
            QMessageBox.information(self, "Sucesso", "Exclusão concluída.")
        self.load_queries()

    def delete_query(self):
        """Exclui uma consulta salva do armazenamento (arquivo consultas.json)."""
        queries = self.qm.list_queries()
        if not queries:
            QMessageBox.information(self, "Informação", "Nenhuma consulta salva encontrada")
            return

        query_names = [q.name for q in queries]
        name, ok = QInputDialog.getItem(
            self,
            "Excluir Consulta",
            "Selecione a consulta a excluir:",
            query_names,
            0,
            False
        )

        if not ok or not name:
            return

        reply = QMessageBox.question(
            self,
            "Confirmação",
            f"Tem certeza que deseja excluir a consulta '{name}'? Esta ação não pode ser desfeita.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        try:
            ok = self.qm.delete_query(name)
            if ok:
                QMessageBox.information(self, "Sucesso", f"Consulta '{name}' excluída com sucesso.")
            else:
                QMessageBox.warning(self, "Falha", f"Não foi possível excluir a consulta '{name}'.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao excluir consulta:\n{str(e)}")

    def open_manage_queries(self):
        """Abre o diálogo de gerenciamento de consultas (listar/renomear/exportar/excluir múltiplas)."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Gerenciar consultas")
        dlg.setMinimumSize(700, 500)

        layout = QVBoxLayout(dlg)

        list_widget = QListWidget()
        list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(list_widget)

        # carrega items com checkbox
        def reload_items():
            list_widget.clear()
            for q in self.qm.list_queries():
                mod = _format_iso_timestamp(q.modified_at)
                it = QListWidgetItem(f"{q.name} — {mod} — {q.description}")
                it.setData(Qt.UserRole, q.name)
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Unchecked)
                list_widget.addItem(it)

        btn_layout = QHBoxLayout()
        btn_rename = QPushButton("Renomear")
        btn_export = QPushButton("Exportar seleção (.sql)")
        btn_delete_sel = QPushButton("Excluir selecionadas")
        btn_close = QPushButton("Fechar")

        btn_layout.addWidget(btn_rename)
        btn_layout.addWidget(btn_export)
        btn_layout.addWidget(btn_delete_sel)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        # Ações
        def get_checked_names() -> list:
            names = []
            for i in range(list_widget.count()):
                it = list_widget.item(i)
                if it.checkState() == Qt.Checked:
                    names.append(it.data(Qt.UserRole))
            return names

        def on_rename():
            checked = get_checked_names()
            if len(checked) != 1:
                QMessageBox.information(dlg, "Renomear", "Selecione exatamente UMA consulta para renomear (marque-a).")
                return
            old = checked[0]
            new, ok = QInputDialog.getText(dlg, "Renomear consulta", f"Novo nome para '{old}':")
            if not ok or not new:
                return
            try:
                self.qm.rename_query(old, new)
                QMessageBox.information(dlg, "Sucesso", f"'{old}' renomeada para '{new}'.")
                reload_items()
            except Exception as e:
                QMessageBox.critical(dlg, "Erro", f"Falha ao renomear: {e}")

        def on_export():
            names = get_checked_names()
            if not names:
                QMessageBox.information(dlg, "Exportar", "Marque ao menos uma consulta para exportar.")
                return
            folder = QFileDialog.getExistingDirectory(dlg, "Selecione pasta para exportar (.sql)")
            if not folder:
                return
            try:
                for name in names:
                    q = self.qm.get_query(name)
                    if not q:
                        continue
                    safe_name = ''.join(c for c in name if c.isalnum() or c in (' ', '_', '-')).rstrip()
                    path = os.path.join(folder, f"{safe_name}.sql")
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(q.sql)
                QMessageBox.information(dlg, "Exportar", f"Exportadas {len(names)} consulta(s) para {folder}.")
            except Exception as e:
                QMessageBox.critical(dlg, "Erro", f"Falha ao exportar: {e}")

        def on_delete_selected():
            names = get_checked_names()
            if not names:
                QMessageBox.information(dlg, "Excluir", "Marque ao menos uma consulta para excluir.")
                return
            reply = QMessageBox.question(dlg, "Confirmar exclusão", f"Excluir {len(names)} consulta(s)? Esta ação é irreversível.", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
            failed = []
            for name in names:
                try:
                    ok = self.qm.delete_query(name)
                    if not ok:
                        failed.append(name)
                except Exception:
                    failed.append(name)
            if failed:
                QMessageBox.warning(dlg, "Excluir", f"Falha ao excluir: {', '.join(failed)}")
            else:
                QMessageBox.information(dlg, "Excluir", f"{len(names)} consulta(s) excluídas com sucesso.")
            reload_items()

        btn_rename.clicked.connect(on_rename)
        btn_export.clicked.connect(on_export)
        btn_delete_sel.clicked.connect(on_delete_selected)
        btn_close.clicked.connect(dlg.accept)

        reload_items()
        dlg.exec_()

class ResultsTab(QWidget):
    """Aba de resultados"""
    
    def __init__(self, ai_generator: AIInsightsGenerator, chart_gen: ChartGenerator, 
                 report_gen: ReportGenerator):
        super().__init__()
        self.ai_gen = ai_generator
        self.chart_gen = chart_gen
        self.report_gen = report_gen
        self.current_data = []
        self.current_columns = []
        self.insights_text = None
        self.chart_figure = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Barra de ferramentas
        toolbar = QHBoxLayout()
        
        self.btn_insights = QPushButton("Gerar Insights com IA")
        self.btn_insights.clicked.connect(self.generate_insights)
        toolbar.addWidget(self.btn_insights)
        
        self.btn_chart = QPushButton("Gerar Gráfico")
        self.btn_chart.clicked.connect(self.generate_chart)
        toolbar.addWidget(self.btn_chart)
        
        self.btn_export = QPushButton("Exportar PDF")
        self.btn_export.clicked.connect(self.export_pdf)
        toolbar.addWidget(self.btn_export)
        
        self.btn_export_csv = QPushButton("Exportar CSV")
        self.btn_export_csv.clicked.connect(self.export_csv)
        toolbar.addWidget(self.btn_export_csv)
        
        self.btn_export_view = QPushButton("Exportar como VIEW")
        self.btn_export_view.clicked.connect(self.export_view)
        toolbar.addWidget(self.btn_export_view)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Tabela de resultados
        self.results_table = QTableWidget()
        self.results_table.setSortingEnabled(True)
        layout.addWidget(self.results_table)
        
        # Status
        self.status_label = QLabel("Nenhum resultado carregado")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def load_data(self, columns: list, data: list):
        """Carrega dados na tabela"""
        self.current_columns = columns
        self.current_data = data
        self.results_table.clear()
        self.results_table.setRowCount(len(data))
        self.results_table.setColumnCount(len(columns))

        # Detect column types based on first non-null value in each column
        col_types = []  # 'numeric', 'date', 'text'
        for col_idx in range(len(columns)):
            ctype = 'text'
            for r in range(len(data)):
                try:
                    val = data[r][col_idx]
                except Exception:
                    val = None
                if val is None:
                    continue
                # numeric
                if isinstance(val, Number):
                    ctype = 'numeric'
                    break
                # datetime/date
                try:
                    import datetime as _d
                    if isinstance(val, (_d.datetime, _d.date)):
                        ctype = 'date'
                        break
                except Exception:
                    pass
                # string that looks like ISO datetime
                try:
                    if isinstance(val, str) and len(val) >= 10 and val[:10].count('-') == 2 and (':' in val or 'T' in val or ' ' in val):
                        ctype = 'date'
                        break
                except Exception:
                    pass
            col_types.append(ctype)

        # set headers with alignment
        for i, col in enumerate(columns):
            hi = QTableWidgetItem(col)
            # estilo do cabeçalho: negrito
            try:
                f = hi.font()
                f.setBold(True)
                hi.setFont(f)
            except Exception:
                pass

            if col_types[i] in ('numeric', 'date'):
                hi.setTextAlignment(Qt.AlignCenter)
            else:
                hi.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.results_table.setHorizontalHeaderItem(i, hi)

        for row_idx, row_data in enumerate(data):
            for col_idx, value in enumerate(row_data):
                display = ""
                align = Qt.AlignLeft | Qt.AlignVCenter
                if value is None:
                    display = ""
                else:
                    if col_types[col_idx] == 'numeric' and isinstance(value, Number):
                        # Use main window preferences for decimal places when available
                        try:
                            main = self.window()
                            decimals = int(getattr(main, 'number_decimals', 2))
                        except Exception:
                            decimals = 2

                        try:
                            # format floats with configured decimals; ints stay as-is
                            if isinstance(value, float):
                                display = f"{value:.{decimals}f}"
                            else:
                                display = str(value)
                        except Exception:
                            display = str(value)

                        align = Qt.AlignCenter
                    elif col_types[col_idx] == 'date':
                        # format date-only using user preference if set in MainWindow
                        try:
                            main = self.window()
                            date_fmt = getattr(main, 'date_format', '%Y-%m-%d')
                        except Exception:
                            date_fmt = '%Y-%m-%d'

                        try:
                            import datetime as _d
                            if isinstance(value, (_d.datetime, _d.date)):
                                display = value.strftime(date_fmt)
                            elif isinstance(value, str):
                                # try to extract date part and reformat if possible
                                raw = value.split('T')[0].split(' ')[0]
                                # try parsing ISO-like YYYY-MM-DD
                                try:
                                    parts = raw.split('-')
                                    if len(parts) == 3:
                                        y, m, d = parts
                                        dt = _d.date(int(y), int(m), int(d))
                                        display = dt.strftime(date_fmt)
                                    else:
                                        display = raw
                                except Exception:
                                    display = raw
                            else:
                                display = str(value)
                        except Exception:
                            display = str(value)

                        align = Qt.AlignCenter
                    else:
                        display = str(value)
                        align = Qt.AlignLeft | Qt.AlignVCenter

                item = QTableWidgetItem(display)
                item.setTextAlignment(align)
                self.results_table.setItem(row_idx, col_idx, item)

        self.results_table.resizeColumnsToContents()
        self.status_label.setText(f"{len(data)} registros carregados")
    
    def generate_insights(self):
        """Gera insights com IA"""
        if not self.current_data:
            QMessageBox.warning(self, "Aviso", "Nenhum dado carregado")
            return
        
        # Verifica API key
        if not self.ai_gen.api_key:
            api_key, ok = QInputDialog.getText(
                self,
                "Chave OpenAI",
                "Insira sua chave da API OpenAI:",
                QLineEdit.Password
            )
            if not ok or not api_key:
                return
            self.ai_gen.set_api_key(api_key)
        
        try:
            # Mostra progresso
            progress = QProgressDialog("Gerando insights...", "Cancelar", 0, 0, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            QApplication.processEvents()
            
            # Gera insights
            self.insights_text = self.ai_gen.generate_insights(
                self.current_data,
                self.current_columns
            )
            
            progress.close()
            
            # Mostra insights
            dialog = QDialog(self)
            dialog.setWindowTitle("Insights Gerados")
            dialog.setMinimumSize(600, 400)
            
            layout = QVBoxLayout()
            text_edit = QTextEdit()
            text_edit.setPlainText(self.insights_text)
            text_edit.setReadOnly(True)
            layout.addWidget(text_edit)
            
            btn_close = QPushButton("Fechar")
            btn_close.clicked.connect(dialog.accept)
            layout.addWidget(btn_close)
            
            dialog.setLayout(layout)
            dialog.exec_()
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao gerar insights:\n{str(e)}")
    
    def generate_chart(self):
        """Gera gráfico"""
        if not self.current_data:
            QMessageBox.warning(self, "Aviso", "Nenhum dado carregado")
            return
        
        # Dialog para configurar gráfico
        dialog = ChartConfigDialog(self.current_columns, self)
        if dialog.exec_() == QDialog.Accepted:
            config = dialog.get_config()
            
            try:
                self.chart_figure = self.chart_gen.create_chart(
                    self.current_data,
                    self.current_columns,
                    config['x_column'],
                    config['y_column'],
                    config['aggregation'],
                    config['chart_type'],
                    config['title']
                )
                
                # Mostra gráfico
                from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
                
                chart_dialog = QDialog(self)
                chart_dialog.setWindowTitle("Gráfico")
                chart_dialog.setMinimumSize(800, 600)
                
                layout = QVBoxLayout()
                canvas = FigureCanvasQTAgg(self.chart_figure)
                layout.addWidget(canvas)
                
                btn_close = QPushButton("Fechar")
                btn_close.clicked.connect(chart_dialog.accept)
                layout.addWidget(btn_close)
                
                chart_dialog.setLayout(layout)
                chart_dialog.exec_()
                
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao gerar gráfico:\n{str(e)}")
    
    def export_pdf(self):
        """Exporta relatório em PDF"""
        if not self.current_data:
            QMessageBox.warning(self, "Aviso", "Nenhum dado carregado")
            return
        
        # Dialog para configurar exportação
        dialog = ExportDialog(self.insights_text is not None, self.chart_figure is not None, self)
        if dialog.exec_() == QDialog.Accepted:
            config = dialog.get_config()
            
            # Salvar arquivo
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Salvar PDF",
                "",
                "PDF Files (*.pdf)"
            )
            
            if not file_path:
                return
            
            try:
                self.report_gen.create_report(
                    output_path=file_path,
                    report_name=config['report_name'],
                    user_name=config['user_name'],
                    orientation=config['orientation'],
                    include_insights=config['include_insights'],
                    insights_text=self.insights_text,
                    include_chart=config['include_chart'],
                    chart_figure=self.chart_figure,
                    include_table=config['include_table'],
                    columns=self.current_columns,
                    data=self.current_data,
                    date_format=getattr(self, 'date_format', '%Y-%m-%d'),
                    number_decimals=int(getattr(self, 'number_decimals', 2))
                )
                
                QMessageBox.information(self, "Sucesso", f"PDF gerado: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao gerar PDF:\n{str(e)}")

    def export_csv(self):
        """Exporta os resultados atuais para CSV usando as preferências de formatação."""
        if not self.current_data:
            QMessageBox.warning(self, "Aviso", "Nenhum dado carregado")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Salvar CSV", "", "CSV Files (*.csv);;All Files (*)")
        if not file_path:
            return

        # obtain preferences from main window if available
        try:
            main = self.window()
            date_fmt = getattr(main, 'date_format', '%Y-%m-%d')
            decimals = int(getattr(main, 'number_decimals', 2))
        except Exception:
            date_fmt = '%Y-%m-%d'
            decimals = 2

        try:
            ok = self.report_gen.create_csv(
                output_path=file_path,
                columns=self.current_columns,
                data=self.current_data,
                date_format=date_fmt,
                number_decimals=decimals
            )
            if ok:
                QMessageBox.information(self, "Sucesso", f"CSV gerado: {file_path}")
            else:
                QMessageBox.critical(self, "Erro", "Falha ao gerar CSV")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao exportar CSV:\n{e}")
    
    def export_view(self):
        """Exporta consulta como VIEW"""
        # Implementar exportação de VIEW SQL
        QMessageBox.information(self, "Informação", "Funcionalidade em desenvolvimento")

"""
Dialogs auxiliares e janela principal do CSData Studio
"""
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from chart_generator import ChartType, AggregationType

class ChartConfigDialog(QDialog):
    """Dialog para configurar o gráfico"""
    
    def __init__(self, columns: list, parent=None):
        super().__init__(parent)
        self.columns = columns
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("Configurar Gráfico")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Coluna X
        layout.addWidget(QLabel("Coluna para Eixo X:"))
        self.x_combo = QComboBox()
        self.x_combo.addItems(self.columns)
        layout.addWidget(self.x_combo)
        
        # Coluna Y
        layout.addWidget(QLabel("Coluna para Eixo Y:"))
        self.y_combo = QComboBox()
        self.y_combo.addItems(self.columns)
        layout.addWidget(self.y_combo)
        
        # Agregação
        layout.addWidget(QLabel("Tipo de Agregação:"))
        self.agg_combo = QComboBox()
        self.agg_combo.addItems(["COUNT", "SUM", "AVG", "MIN", "MAX"])
        layout.addWidget(self.agg_combo)
        
        # Tipo de gráfico
        layout.addWidget(QLabel("Tipo de Gráfico:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Colunas", "Barras"])
        layout.addWidget(self.type_combo)
        
        # Título
        layout.addWidget(QLabel("Título:"))
        self.title_input = QLineEdit()
        self.title_input.setText("Gráfico de Dados")
        layout.addWidget(self.title_input)
        
        # Botões
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_config(self):
        """Retorna configuração do gráfico"""
        agg_map = {
            "COUNT": AggregationType.COUNT,
            "SUM": AggregationType.SUM,
            "AVG": AggregationType.AVG,
            "MIN": AggregationType.MIN,
            "MAX": AggregationType.MAX
        }
        
        type_map = {
            "Colunas": ChartType.COLUMN,
            "Barras": ChartType.BAR
        }
        
        return {
            'x_column': self.x_combo.currentText(),
            'y_column': self.y_combo.currentText(),
            'aggregation': agg_map[self.agg_combo.currentText()],
            'chart_type': type_map[self.type_combo.currentText()],
            'title': self.title_input.text()
        }


class PreferencesDialog(QDialog):
    """Dialog para preferências de usuário: formatação de datas e números."""

    def __init__(self, parent=None, date_format='%Y-%m-%d', number_decimals=2):
        super().__init__(parent)
        self.setWindowTitle('Preferências')
        self.date_format = date_format
        self.number_decimals = number_decimals
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel('Formato de data:'))
        self.date_combo = QComboBox()
        self.date_combo.addItem('YYYY-MM-DD', '%Y-%m-%d')
        self.date_combo.addItem('DD/MM/YYYY', '%d/%m/%Y')
        # set current
        idx = 0 if self.date_format == '%Y-%m-%d' else 1
        self.date_combo.setCurrentIndex(idx)
        layout.addWidget(self.date_combo)

        layout.addWidget(QLabel('Casas decimais para números:'))
        from PyQt5.QtWidgets import QSpinBox
        self.dec_spin = QSpinBox()
        self.dec_spin.setRange(0, 8)
        self.dec_spin.setValue(self.number_decimals)
        layout.addWidget(self.dec_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        return self.date_combo.currentData(), self.dec_spin.value()

class ExportDialog(QDialog):
    """Dialog para configurar exportação de PDF"""
    
    def __init__(self, has_insights: bool, has_chart: bool, parent=None):
        super().__init__(parent)
        self.has_insights = has_insights
        self.has_chart = has_chart
        self.setup_ui()
    
    def setup_ui(self):
        self.setWindowTitle("Exportar PDF")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Nome do relatório
        layout.addWidget(QLabel("Nome do Relatório (obrigatório):"))
        self.report_name_input = QLineEdit()
        self.report_name_input.setPlaceholderText("Ex: Relatório de Vendas 2024")
        layout.addWidget(self.report_name_input)
        
        # Nome do usuário
        layout.addWidget(QLabel("Nome do Usuário:"))
        self.user_name_input = QLineEdit()
        self.user_name_input.setText("Usuário")
        layout.addWidget(self.user_name_input)
        
        # Orientação
        layout.addWidget(QLabel("Orientação:"))
        orientation_group = QWidget()
        orientation_layout = QHBoxLayout()
        self.portrait_radio = QRadioButton("Retrato")
        self.landscape_radio = QRadioButton("Paisagem")
        self.portrait_radio.setChecked(True)
        orientation_layout.addWidget(self.portrait_radio)
        orientation_layout.addWidget(self.landscape_radio)
        orientation_group.setLayout(orientation_layout)
        layout.addWidget(orientation_group)
        
        # Itens a incluir
        layout.addWidget(QLabel("Incluir no PDF:"))
        
        self.include_insights_cb = QCheckBox("Insights da IA")
        self.include_insights_cb.setEnabled(self.has_insights)
        self.include_insights_cb.setChecked(self.has_insights)
        layout.addWidget(self.include_insights_cb)
        
        self.include_chart_cb = QCheckBox("Gráfico")
        self.include_chart_cb.setEnabled(self.has_chart)
        self.include_chart_cb.setChecked(self.has_chart)
        layout.addWidget(self.include_chart_cb)
        
        self.include_table_cb = QCheckBox("Tabela de Resultados")
        self.include_table_cb.setChecked(True)
        layout.addWidget(self.include_table_cb)
        
        # Botões
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def validate_and_accept(self):
        """Valida antes de aceitar"""
        if not self.report_name_input.text().strip():
            QMessageBox.warning(self, "Aviso", "Nome do relatório é obrigatório")
            return
        self.accept()
    
    def get_config(self):
        """Retorna configuração da exportação"""
        return {
            'report_name': self.report_name_input.text().strip(),
            'user_name': self.user_name_input.text().strip(),
            'orientation': 'landscape' if self.landscape_radio.isChecked() else 'portrait',
            'include_insights': self.include_insights_cb.isChecked(),
            'include_chart': self.include_chart_cb.isChecked(),
            'include_table': self.include_table_cb.isChecked()
        }

class MainWindow(QMainWindow):
    """Janela principal do CSData Studio"""
    
    def __init__(self, user_data: dict, db_config: DatabaseConfig):
        super().__init__()
        self.user_data = user_data
        self.db_config = db_config
        self.conn = None
        self.setup_connection()
        self.setup_ui()
    
    def setup_connection(self):
        """Estabelece conexão com o banco"""
        try:
            self.conn = get_db_connection(self.db_config)
        except Exception as e:
            # Log detalhado no terminal para debug
            logging.exception("Erro ao conectar ao banco")
            QMessageBox.critical(self, "Erro", f"Erro ao conectar ao banco:\n{str(e)}")
            sys.exit(1)
    
    def setup_ui(self):
        """Configura a interface"""
        self.setWindowTitle(f"{APP_NAME} v{Version.get_version()}")
        self.setMinimumSize(1200, 800)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        
        # Barra de informações
        info_bar = QHBoxLayout()
        info_bar.addWidget(QLabel(f"<b>Usuário:</b> {self.user_data['NomeUsuario']}"))
        info_bar.addWidget(QLabel(f"<b>Banco:</b> {self.db_config.db_name}"))
        info_bar.addWidget(QLabel(f"<b>Servidor:</b> {self.db_config.server_name}"))
        info_bar.addStretch()
        layout.addLayout(info_bar)
        
        # Tabs
        tabs = QTabWidget()
        
        # Inicializa componentes
        query_builder = QueryBuilder(self.conn)
        query_manager = QueryManager()
        ai_generator = AIInsightsGenerator()
        chart_generator = ChartGenerator()
        report_generator = ReportGenerator()

        # create session logger for the logged user
        try:
            login_em = self.user_data.get('LoginEm') if self.user_data else None
            self.session_logger = SessionLogger(self.user_data.get('NomeUsuario') if self.user_data else 'unknown', login_em)
        except Exception:
            self.session_logger = None

        # Aba 1: Query Builder
        self.query_tab = QueryBuilderTab(query_builder, query_manager, session_logger=self.session_logger)
        tabs.addTab(self.query_tab, "Construtor de Consultas")
        
        # Aba 2: Resultados
        self.results_tab = ResultsTab(ai_generator, chart_generator, report_generator)
        tabs.addTab(self.results_tab, "Resultados e Análise")
        
        # Conecta sinais
        self.query_tab.query_executed.connect(self.on_query_executed)
        
        layout.addWidget(tabs)
        
        central_widget.setLayout(layout)
        
        # Menu
        self.create_menus()
        
        # Status bar
        self.statusBar().showMessage("Pronto")
    
    def create_menus(self):
        """Cria menus"""
        menubar = self.menuBar()
        
        # Menu Arquivo
        file_menu = menubar.addMenu("Arquivo")
        manage_action = QAction("Gerenciar consultas", self)
        manage_action.triggered.connect(lambda: self.open_manage_queries())
        file_menu.addAction(manage_action)
        file_menu.addSeparator()
        exit_action = QAction("Sair", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Menu Ferramentas
        tools_menu = menubar.addMenu("Ferramentas")
        
        config_api_action = QAction("Configurar API OpenAI", self)
        config_api_action.triggered.connect(self.configure_api)
        tools_menu.addAction(config_api_action)

        prefs_action = QAction("Preferências", self)
        prefs_action.triggered.connect(self.open_preferences)
        tools_menu.addAction(prefs_action)
        
        # Menu Ajuda
        help_menu = menubar.addMenu("Ajuda")
        
        about_action = QAction("Sobre", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def on_query_executed(self, columns: list, data: list):
        """Callback quando consulta é executada"""
        self.results_tab.load_data(columns, data)
        # Muda para aba de resultados
        self.centralWidget().layout().itemAt(1).widget().setCurrentIndex(1)
    
    def configure_api(self):
        """Configura chave da API OpenAI"""
        api_key, ok = QInputDialog.getText(
            self,
            "Configurar API OpenAI",
            "Insira sua chave da API OpenAI:",
            QLineEdit.Password
        )
        if ok and api_key:
            self.results_tab.ai_gen.set_api_key(api_key)
            QMessageBox.information(self, "Sucesso", "Chave da API configurada!")
    
    def show_about(self):
        """Mostra diálogo Sobre"""
        QMessageBox.about(
            self,
            "Sobre",
            f"""<h2>{APP_NAME}</h2>
            <p><b>Versão:</b> {Version.get_version()}</p>
            <p><b>Empresa:</b> {COMPANY_NAME}</p>
            <p>Sistema de Business Intelligence e Análise de Dados</p>
            <p>Desenvolvido com Python e PyQt5</p>
            """
        )

    def open_preferences(self):
        """Abre diálogo de preferências e aplica configurações ao MainWindow."""
        # current values or defaults
        current_date_fmt = getattr(self, 'date_format', '%Y-%m-%d')
        current_dec = getattr(self, 'number_decimals', 2)
        dlg = PreferencesDialog(self, date_format=current_date_fmt, number_decimals=current_dec)
        if dlg.exec_() == QDialog.Accepted:
            date_fmt, dec = dlg.get_values()
            self.date_format = date_fmt
            self.number_decimals = dec
            QMessageBox.information(self, 'Preferências', 'Preferências atualizadas.')
    
    def closeEvent(self, event):
        """Evento de fechamento"""
        # fecha conexão com o banco
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass

        # fecha e empacota o log de sessão, se existir
        try:
            if getattr(self, 'session_logger', None):
                try:
                    self.session_logger.close_session()
                except Exception:
                    pass
        except Exception:
            pass

        event.accept()

    def open_manage_queries(self):
        """Abre o diálogo de gerenciamento de consultas."""
        try:
            dlg = ManageQueriesDialog(self, QueryManager())
            dlg.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao abrir Gerenciador de Consultas:\n{e}")

def main():
    """Função principal"""
    # Configura logging para DEBUG no terminal para facilitar debug
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # Excepthook para logar exceções não tratadas no terminal antes do GUI
    def _excepthook(exc_type, exc_value, exc_tb):
        logging.exception("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        # Chama excepthook padrão também
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook

    logging.debug('Iniciando aplicação CSData Studio')

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    # set application icon from assets if available
    try:
        icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'logo.ico')
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
    except Exception:
        pass
    
    # Lê todas as opções de configuração de banco (pode haver várias entradas <database>)
    db_options = ConfigManager.read_all_configs()
    if not db_options:
        QMessageBox.critical(
            None,
            "Erro",
            f"Não foi possível ler o arquivo de configuração:\n{ConfigManager.CONFIG_PATH}"
        )
        sys.exit(1)

    # Login (mostra seleção de banco quando houver mais de uma opção)
    login_dialog = LoginDialog(db_options=db_options)
    if login_dialog.exec_() != QDialog.Accepted:
        sys.exit(0)
    
    user_data = login_dialog.user_data
    selected_db = getattr(login_dialog, 'selected_db', None) or ConfigManager.read_config()

    # Janela principal
    window = MainWindow(user_data, selected_db)
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()