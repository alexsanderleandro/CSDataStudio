"""
CSData Studio - Aplicação Principal
Sistema de Business Intelligence e Análise de Dados
"""
import sys
import os
import logging
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

# Imports dos módulos do projeto
from version import Version, APP_NAME, COMPANY_NAME
from config_manager import ConfigManager, DatabaseConfig
from authentication import get_db_connection, verify_user
from consulta_sql import QueryBuilder, JoinType, TableInfo
from saved_queries import QueryManager, SavedQuery
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
        
        # Enter para login
        self.password_input.returnPressed.connect(self.handle_login)
    
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

                # Valida usando Trusted Connection
                user_data = verify_user(None, None, selected_cfg)

            else:
                # Para SQLSERVER (ou padrão), exige username+password (SQL Auth)
                if not username or not password:
                    QMessageBox.warning(
                        self,
                        "Credenciais necessárias",
                        "Preencha Usuário e Senha para autenticação SQL (TipoBanco=SQLSERVER)."
                    )
                    return

                user_data = verify_user(username, password, selected_cfg)

            if user_data:
                # Verifica permissões básicas: apenas checamos se o usuário está ativo
                if user_data.get('InativosN', 0) != 0:
                    QMessageBox.critical(
                        self,
                        "Sem Permissão",
                        "Usuário inativo. Contate o administrador para ativar a conta."
                    )
                    return

                self.user_data = user_data
                self.selected_db = selected_cfg
                self.accept()
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

class QueryBuilderTab(QWidget):
    """Aba de construção de consultas"""
    
    query_executed = pyqtSignal(list, list)  # (columns, data)
    
    def __init__(self, query_builder: QueryBuilder, query_manager: QueryManager):
        super().__init__()
        self.qb = query_builder
        self.qm = query_manager
        self.selected_tables = []
        self.selected_columns = []
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout()
        
        # === PAINEL ESQUERDO: Seleção ===
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        # Tabelas disponíveis
        left_layout.addWidget(QLabel("<b>Tabelas e Views:</b>"))
        self.tables_list = QListWidget()
        self.tables_list.setSelectionMode(QListWidget.MultiSelection)
        left_layout.addWidget(self.tables_list)
        
        # Botão para adicionar tabelas
        btn_add_tables = QPushButton("Adicionar Tabelas Selecionadas")
        btn_add_tables.clicked.connect(self.add_selected_tables)
        left_layout.addWidget(btn_add_tables)
        
        left_panel.setLayout(left_layout)
        
        # === PAINEL CENTRAL: Tabelas e Colunas Selecionadas ===
        center_panel = QWidget()
        center_layout = QVBoxLayout()
        
        center_layout.addWidget(QLabel("<b>Tabelas Selecionadas:</b>"))
        self.selected_tables_list = QListWidget()
        center_layout.addWidget(self.selected_tables_list)
        
        # Botões para gerenciar tabelas
        btn_layout = QHBoxLayout()
        btn_remove_table = QPushButton("Remover Tabela")
        btn_remove_table.clicked.connect(self.remove_selected_table)
        btn_layout.addWidget(btn_remove_table)
        
        btn_clear_tables = QPushButton("Limpar Tudo")
        btn_clear_tables.clicked.connect(self.clear_selection)
        btn_layout.addWidget(btn_clear_tables)
        center_layout.addLayout(btn_layout)
        
        center_layout.addWidget(QLabel("<b>Colunas Disponíveis:</b>"))
        self.columns_list = QListWidget()
        self.columns_list.setSelectionMode(QListWidget.MultiSelection)
        center_layout.addWidget(self.columns_list)
        
        btn_add_columns = QPushButton("Adicionar Colunas")
        btn_add_columns.clicked.connect(self.add_selected_columns)
        center_layout.addWidget(btn_add_columns)
        
        center_panel.setLayout(center_layout)
        
        # === PAINEL DIREITO: Configurações e Execução ===
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        right_layout.addWidget(QLabel("<b>Colunas Selecionadas:</b>"))
        self.selected_columns_list = QListWidget()
        right_layout.addWidget(self.selected_columns_list)
        
        btn_remove_column = QPushButton("Remover Coluna")
        btn_remove_column.clicked.connect(self.remove_selected_column)
        right_layout.addWidget(btn_remove_column)
        
        # Tipo de JOIN
        right_layout.addWidget(QLabel("<b>Tipo de JOIN:</b>"))
        self.join_type_combo = QComboBox()
        self.join_type_combo.addItems(["INNER JOIN", "LEFT JOIN", "RIGHT JOIN"])
        right_layout.addWidget(self.join_type_combo)
        
        # Cláusula WHERE
        right_layout.addWidget(QLabel("<b>Cláusula WHERE:</b>"))
        self.where_input = QTextEdit()
        self.where_input.setPlaceholderText("Ex: DataVenda >= '2024-01-01'")
        self.where_input.setMaximumHeight(100)
        right_layout.addWidget(self.where_input)
        
        # SQL Gerada
        right_layout.addWidget(QLabel("<b>SQL Gerada:</b>"))
        self.sql_preview = QTextEdit()
        self.sql_preview.setReadOnly(True)
        self.sql_preview.setMaximumHeight(150)
        right_layout.addWidget(self.sql_preview)
        
        # Botões de ação
        action_layout = QVBoxLayout()
        # Opções de alias
        alias_layout = QHBoxLayout()
        self.use_alias_cb = QCheckBox("Usar aliases")
        self.use_alias_cb.setChecked(True)
        alias_layout.addWidget(self.use_alias_cb)

        self.alias_style_combo = QComboBox()
        self.alias_style_combo.addItems(["Curto (apg,cli)", "Descritivo (apagar,clientes)", "Nenhum (nomes qualificados)"])
        alias_layout.addWidget(self.alias_style_combo)
        action_layout.addLayout(alias_layout)
        
        btn_generate = QPushButton("Gerar SQL")
        btn_generate.clicked.connect(self.generate_sql)
        action_layout.addWidget(btn_generate)
        
        btn_execute = QPushButton("Executar Consulta")
        btn_execute.clicked.connect(self.execute_query)
        btn_execute.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        action_layout.addWidget(btn_execute)
        
        btn_save = QPushButton("Salvar Consulta")
        btn_save.clicked.connect(self.save_query)
        action_layout.addWidget(btn_save)
        
        btn_load = QPushButton("Carregar Consulta")
        btn_load.clicked.connect(self.load_query)
        action_layout.addWidget(btn_load)
        
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
        self.load_tables()
        # estado para tooltip persistente
        self._details_dialog = None
        self._last_hovered_table = None
        # Duplo clique: adiciona automaticamente
        self.tables_list.itemDoubleClicked.connect(lambda _ : self.add_selected_tables())
        self.columns_list.itemDoubleClicked.connect(lambda _ : self.add_selected_columns())
        # Menu de contexto na lista de colunas para inserir no WHERE
        self.columns_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.columns_list.customContextMenuRequested.connect(self.on_columns_context_menu)
        # Tooltip/hover para mostrar dependências
        self.tables_list.setMouseTracking(True)
        self.tables_list.viewport().installEventFilter(self)
        # Clique em tabela selecionada mostra apenas suas colunas disponíveis
        self.selected_tables_list.itemClicked.connect(self.on_selected_table_clicked)
    
    def load_tables(self):
        """Carrega tabelas e views do banco"""
        try:
            tables = self.qb.get_tables_and_views()
            self.tables_list.clear()
            for table in tables:
                item_text = f"[{table.schema}].{table.name} ({table.type})"
                self.tables_list.addItem(item_text)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao carregar tabelas:\n{str(e)}")
    
    def add_selected_tables(self):
        """Adiciona tabelas selecionadas"""
        selected_items = self.tables_list.selectedItems()
        if not selected_items:
            return
        
        for item in selected_items:
            if item.text() not in [self.selected_tables_list.item(i).text() 
                                  for i in range(self.selected_tables_list.count())]:
                self.selected_tables_list.addItem(item.text())
        
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
            table_text = self.selected_tables_list.item(i).text()
            # Parse: [schema].table (TYPE)
            parts = table_text.split('.')
            schema = parts[0].strip('[]')
            table_name = parts[1].split('(')[0].strip()
            
            try:
                columns = self.qb.get_table_columns(schema, table_name)
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

            # tenta encontrar schema nas tabelas selecionadas
            schema = 'dbo'
            for i in range(self.selected_tables_list.count()):
                ttext = self.selected_tables_list.item(i).text()
                tparts = ttext.split('.')
                t_schema = tparts[0].strip('[]')
                t_name = tparts[1].split('(')[0].strip()
                if t_name.lower() == table_name.lower():
                    schema = t_schema
                    break

            # busca tipo de dado da coluna para sugerir operador/format
            data_type = None
            try:
                cols = self.qb.get_table_columns(schema, table_name)
                for c in cols:
                    if c.column_name.lower() == col_name.lower():
                        data_type = (c.data_type or '').lower()
                        break
            except Exception:
                data_type = None

            # cria referência qualificada
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

            value_edit = QLineEdit()
            value_edit.setPlaceholderText("Valor (deixe em branco para inserir placeholder)")
            vlayout.addWidget(QLabel("Valor:"))
            vlayout.addWidget(value_edit)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            vlayout.addWidget(buttons)
            buttons.accepted.connect(dlg.accept)
            buttons.rejected.connect(dlg.reject)

            if dlg.exec_() == QDialog.Accepted:
                op = op_combo.currentText()
                val = value_edit.text().strip()
                # monta expressão conforme operador
                expr = ""
                needs_quotes = False
                if data_type and any(t in data_type for t in ("char", "text", "varchar", "nchar", "nvarchar")):
                    needs_quotes = True
                if op == "IS NULL":
                    expr = f"{field_ref} IS NULL"
                elif op == "IN":
                    if val:
                        # split by comma
                        parts = [p.strip() for p in val.split(',') if p.strip()]
                        if needs_quotes:
                            parts = [f"'{p}'" for p in parts]
                        expr = f"{field_ref} IN ({', '.join(parts)})"
                    else:
                        expr = f"{field_ref} IN ('')"
                elif op == "BETWEEN":
                    if val:
                        # expect user to provide two values separated by comma
                        parts = [p.strip() for p in val.split(',')]
                        if len(parts) >= 2:
                            a, b = parts[0], parts[1]
                            if needs_quotes:
                                a = f"'{a}'"; b = f"'{b}'"
                            expr = f"{field_ref} BETWEEN {a} AND {b}"
                        else:
                            if needs_quotes:
                                expr = f"{field_ref} BETWEEN '' AND ''"
                            else:
                                expr = f"{field_ref} BETWEEN  AND "
                    else:
                        if needs_quotes:
                            expr = f"{field_ref} BETWEEN '' AND ''"
                        else:
                            expr = f"{field_ref} BETWEEN  AND "
                else:
                    # operators like =, <>, >, <, >=, <=, LIKE
                    if val:
                        if needs_quotes:
                            v = f"'{val}'"
                        else:
                            v = val
                        expr = f"{field_ref} {op} {v}"
                    else:
                        # placeholder
                        if needs_quotes:
                            expr = f"{field_ref} {op} ''"
                        else:
                            expr = f"{field_ref} {op} "

                # insere no where_input
                current = self.where_input.toPlainText()
                if not current.strip():
                    self.where_input.setPlainText(expr)
                else:
                    cursor = self.where_input.textCursor()
                    # add space and AND
                    cursor.insertText(f" AND {expr}")
                    self.where_input.setTextCursor(cursor)
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
            table_text = item.text()
            parts = table_text.split('.')
            schema = parts[0].strip('[]')
            table_name = parts[1].split('(')[0].strip()

            # Limpa colunas disponíveis e carrega apenas desta tabela
            self.columns_list.clear()
            columns = self.qb.get_table_columns(schema, table_name)
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
                table_text = self.selected_tables_list.item(i).text()
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

            # Gera SQL
            sql = self.qb.build_query(tables, columns, None, where_clause, alias_mode=alias_mode)
            # Se não houver filtros, exibe comentário informativo no preview
            if not where_clause:
                preview = "-- Sem filtros aplicados\n" + sql
            else:
                preview = sql
            self.sql_preview.setPlainText(preview)
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao gerar SQL:\n{str(e)}")
    
    def execute_query(self):
        """Executa a consulta"""
        sql = self.sql_preview.toPlainText().strip()
        
        if not sql:
            QMessageBox.warning(self, "Aviso", "Gere a SQL primeiro")
            return
        
        # Valida SQL
        is_valid, error_msg = validar_sql(sql)
        if not is_valid:
            QMessageBox.critical(
                self,
                "SQL Inválida",
                f"A consulta não passou na validação de segurança:\n\n{error_msg}"
            )
            return
        
        try:
            columns, data = self.qb.execute_query(sql)
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
        
        # Valida para salvamento
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
            
            QMessageBox.information(self, "Sucesso", "Consulta salva com sucesso!")
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar consulta:\n{str(e)}")
    
    def load_query(self):
        """Carrega uma consulta salva"""
        queries = self.qm.list_queries()
        
        if not queries:
            QMessageBox.information(self, "Info", "Nenhuma consulta salva encontrada")
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
            QMessageBox.information(
                self,
                "Consulta Carregada",
                f"Nome: {query.name}\n"
                f"Descrição: {query.description}\n"
                f"Criada: {query.created_at}"
            )

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
        self.results_table.setHorizontalHeaderLabels(columns)
        
        for row_idx, row_data in enumerate(data):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value) if value is not None else "")
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
                    data=self.current_data
                )
                
                QMessageBox.information(self, "Sucesso", f"PDF gerado: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao gerar PDF:\n{str(e)}")
    
    def export_view(self):
        """Exporta consulta como VIEW"""
        # Implementar exportação de VIEW SQL
        QMessageBox.information(self, "Info", "Funcionalidade em desenvolvimento")

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
        
        # Aba 1: Query Builder
        self.query_tab = QueryBuilderTab(query_builder, query_manager)
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
        
        exit_action = QAction("Sair", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Menu Ferramentas
        tools_menu = menubar.addMenu("Ferramentas")
        
        config_api_action = QAction("Configurar API OpenAI", self)
        config_api_action.triggered.connect(self.configure_api)
        tools_menu.addAction(config_api_action)
        
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
    
    def closeEvent(self, event):
        """Evento de fechamento"""
        if self.conn:
            self.conn.close()
        event.accept()

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