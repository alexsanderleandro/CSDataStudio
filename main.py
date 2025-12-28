from PyQt5.QtWidgets import QMenu, QAction, QListWidgetItem, QApplication
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QEvent, QTimer, QDate, QObject, QPropertyAnimation
from PyQt5.QtGui import QIcon, QFont, QColor, QFontMetrics
from PyQt5.QtWidgets import QToolTip, QDialog, QVBoxLayout, QTextEdit, QGraphicsOpacityEffect
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QComboBox, QDialogButtonBox, QMessageBox,
    QCheckBox, QHBoxLayout, QListWidget, QPushButton, QGroupBox,
    QDateEdit, QDoubleSpinBox, QSpinBox, QFileDialog, QInputDialog,
    QProgressDialog, QToolButton, QScrollArea
)
from PyQt5.QtWidgets import QSizePolicy
from numbers import Number
import logging
import sys
import os
from pathlib import Path
import re
import datetime as _dt
import json
from typing import Optional, List
from PyQt5.QtWidgets import QHBoxLayout

# Imports dos módulos do projeto
from version import Version, APP_NAME, COMPANY_NAME
from config_manager import ConfigManager, DatabaseConfig
from authentication import get_db_connection, verify_user
from consulta_sql import QueryBuilder, JoinType
from log import SessionLogger
from saved_queries import QueryManager, SavedQuery
from excecao import IMPEDING_COLUMNS
from chart_generator import ChartGenerator, ChartType, AggregationType
from ai_insights import AIInsightsGenerator
from report_generator import ReportGenerator
from valida_sql import validar_sql, validar_sql_for_save
# optional mapping overrides for friendly labels
try:
    from mapping import get_field_label
except Exception:
    def get_field_label(module, field_name):
        return None

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
        # Ajusta título da janela para mostrar nome reduzido da empresa + indicador de tela
        self.setWindowTitle("CEOsoftware ® | Login")
        try:
            # remover o botão de ajuda (?) na barra de título, se presente
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        except Exception:
            pass
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout()

        # Título principal: mostrar apenas o nome do app (mantendo estilo preto)
        title = QLabel(f"<h2 style='color:#000000; margin:0;'>{APP_NAME}</h2>")
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

        # carregar preferências locais (último DB e usuário) e preencher campos
        try:
            self._local_prefs = self._load_local_prefs()
            matched_db = False
            user_loaded = False
            if getattr(self, 'db_combo', None) and isinstance(self._local_prefs, dict):
                last_db = self._local_prefs.get('last_db')
                if last_db:
                    # tentar selecionar pelo texto armazenado
                    for i in range(self.db_combo.count()):
                        try:
                            if self.db_combo.itemText(i) == last_db:
                                self.db_combo.setCurrentIndex(i)
                                matched_db = True
                                break
                        except Exception:
                            continue
            try:
                last_user = self._local_prefs.get('last_user') if isinstance(self._local_prefs, dict) else None
                if last_user:
                    self.username_input.setText(last_user)
                    user_loaded = True
            except Exception:
                pass

            # Se conseguimos preencher último DB e usuário, posicionar foco na senha
            try:
                if matched_db and user_loaded:
                    # usar QTimer.singleShot para garantir foco após o diálogo ser exibido
                    QTimer.singleShot(0, lambda: self.password_input.setFocus())
            except Exception:
                try:
                    self.password_input.setFocus()
                except Exception:
                    pass
        except Exception:
            pass

    def handle_login(self):
        """Processa o login"""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        # Seleciona DB escolhido primeiro
        selected_cfg = None
        if self.db_combo:
            try:
                idx = self.db_combo.currentIndex()
                selected_cfg = self.db_options[idx]
            except Exception:
                selected_cfg = None
        else:
            try:
                selected_cfg = ConfigManager.read_config()
            except Exception:
                selected_cfg = None

        if not selected_cfg:
            QMessageBox.critical(self, "Erro", "Nenhuma configuração de banco disponível.")
            return

        try:
            # valida usuário (verify_user trata SA/Trusted conforme tipo)
            user_data, reason = verify_user(username or None, password or None, selected_cfg, return_reason=True)
            if user_data:
                self.user_data = user_data
                self.selected_db = selected_cfg
                try:
                    # salvar preferências locais: último DB (texto) e usuário
                    try:
                        last_db_text = self.db_combo.itemText(self.db_combo.currentIndex()) if getattr(self, 'db_combo', None) else None
                    except Exception:
                        last_db_text = None
                    try:
                        last_user = self.username_input.text().strip()
                    except Exception:
                        last_user = None
                    try:
                        self._save_local_prefs({'last_db': last_db_text, 'last_user': last_user})
                    except Exception:
                        pass
                except Exception:
                    pass
                self.accept()
                return

            # sem usuário válido: mostrar razão se disponível
            if reason:
                if reason == 'inactive':
                    QMessageBox.critical(self, 'Sem Permissão', 'Usuário inativo. Contate o administrador.')
                elif reason == 'insufficient_level':
                    QMessageBox.critical(self, 'Sem Permissão', 'Acesso restrito: nível insuficiente.')
                elif reason == 'invalid_credentials':
                    QMessageBox.critical(self, 'Erro de Login', 'Usuário ou senha inválidos.')
                else:
                    QMessageBox.critical(self, 'Erro de Login', 'Falha ao validar usuário. Contate o administrador.')
            else:
                QMessageBox.critical(self, 'Erro de Login', 'Usuário ou senha inválidos.')
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao conectar/validar no banco selecionado:\n{e}')

    def _prefs_path(self):
        """Retorna o caminho completo para o prefs JSON (cria pasta c:\\ceosoftware se necessário)."""
        try:
            base = Path(r'c:\\ceosoftware')
            try:
                base.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            return base / 'csdatastudio.json'
        except Exception:
            return Path('csdatastudio.json')

    def _load_local_prefs(self) -> dict:
        p = self._prefs_path()
        try:
            if p.exists():
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f) or {}
        except Exception:
            pass
        # criar arquivo padrão se não existir
        try:
            data = {'last_db': None, 'last_user': None}
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return data
        except Exception:
            return {}

    def _save_local_prefs(self, d: dict):
        try:
            p = self._prefs_path()
            try:
                cur = {}
                if p.exists():
                    try:
                        with open(p, 'r', encoding='utf-8') as f:
                            cur = json.load(f) or {}
                    except Exception:
                        cur = {}
                # atualiza com chaves fornecidas
                cur.update({k: v for k, v in (d or {}).items() if v is not None})
                with open(p, 'w', encoding='utf-8') as f:
                    json.dump(cur, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        except Exception:
            pass

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
            try:
                QMessageBox.critical(self, "Erro de conexão", f"Erro ao testar conexão:\n{err_msg}")
            except Exception:
                pass
            return

    
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
        # filtros parametrizados construídos via UI (cada item: (expr, params, meta?))
        self._param_filters = []
        # histórico de valores do WHERE para undo (pilha, multi-nível)
        self._where_history = []
        self._where_redo = []
        self._where_history_limit = 50
        # Carrega mapeamento de nomes amigáveis (se houver)
        self._table_name_map = {}
        # cache de colunas por tabela (chave: 'schema.table') para reduzir consultas ao banco
        self._columns_cache = {}
        # debug flag: ativar logs temporários para depuração da população de filtros
        self._debug_filter_populate = True
        self.setup_ui()

    def _prettify_field_label(self, raw_name: str) -> str:
        """Gera um rótulo amigável para um nome técnico de campo.

        Regras simples:
        - Se começar com 'cod' (case-insensitive) -> prefixa com 'Código ' + resto formatado
        - Caso contrário, converte CamelCase / snake_case em palavras separadas
        """
        try:
            if not raw_name:
                return ''
            s = str(raw_name).strip()
            # se já parece um label legível, retorne (tem espaços)
            if ' ' in s:
                return s
            # tratar formatos [schema].[table].[column]
            if '.' in s or '[' in s:
                parts = re.split(r"\.|\[|\]", s)
                parts = [p for p in parts if p]
                s = parts[-1] if parts else s
            # detectar prefixo cod
            if re.match(r'^(cod|codigo)', s, re.IGNORECASE):
                # remover prefixo cod/ codigo
                rest = re.sub(r'^(cod|codigo)_?', '', s, flags=re.IGNORECASE)
                # split camelCase / snake_case
                words = re.sub('([a-z0-9])([A-Z])', r'\1 \2', rest)
                words = words.replace('_', ' ').strip()
                words = words.lower()
                # capitalizar primeira letra
                if words:
                    return 'Código ' + words
                else:
                    return 'Código'
            # default: split camelCase and underscores
            words = re.sub('([a-z0-9])([A-Z])', r'\1 \2', s)
            words = words.replace('_', ' ')
            return words[0].upper() + words[1:] if words else s
        except Exception:
            return raw_name

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
        # layout principal: barra superior (modo) + splitter abaixo
        layout = QVBoxLayout()
        # ajustar margens e espaçamento principais
        try:
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(8)
        except Exception:
            pass

        # (modo radios are inserted later into the actions panel)
        
        # cria a barra superior que conterá os controles de modo (rádios/help)
        top_bar = QWidget()
        try:
            top_bar_layout = QHBoxLayout(top_bar)
            top_bar_layout.setContentsMargins(6, 2, 6, 2)
            top_bar_layout.setSpacing(8)
        except Exception:
            top_bar_layout = QHBoxLayout(top_bar)

        # === PAINEL ESQUERDO: Seleção ===
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        try:
            left_layout.setContentsMargins(6, 6, 6, 6)
            left_layout.setSpacing(6)
        except Exception:
            pass
        
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
        # ajustar tamanho: largura maior, altura reduzida
        try:
            self.table_search.setMinimumWidth(340)
            self.table_search.setFixedHeight(28)
        except Exception:
            pass
        left_layout.addWidget(self.table_search)

        self.tables_list = QListWidget()
        self.tables_list.setSelectionMode(QListWidget.MultiSelection)
        # Menu de contexto para tabelas: permitir Mostrar dependências via botão direito
        self.tables_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tables_list.customContextMenuRequested.connect(self.on_tables_context_menu)
        # altura mínima da lista de tabelas para melhor visibilidade
        try:
            self.tables_list.setMinimumHeight(220)
        except Exception:
            pass
        left_layout.addWidget(self.tables_list)
        
    # (Botão 'Adicionar fontes selecionadas' removido - operação feita via duplo-clique/toggle)
        # Fontes de dados escolhidas (mover aqui, abaixo do campo de pesquisa)
        left_layout.addWidget(QLabel("<b>📌 Fontes de dados escolhidas</b>"))
        self.selected_tables_list = QListWidget()
        try:
            self.selected_tables_list.setMaximumHeight(140)
        except Exception:
            pass
        left_layout.addWidget(self.selected_tables_list)
        
        # Botões para gerenciar tabelas (mover para abaixo de 'Fontes de dados escolhidas')
        tbl_btns = QHBoxLayout()
        btn_remove_table = QPushButton("➖ Remover fonte")
        btn_remove_table.clicked.connect(self.remove_selected_table)
        tbl_btns.addWidget(btn_remove_table)
        self.btn_remove_table = btn_remove_table

        btn_clear_tables = QPushButton("🧹 Limpar tudo")
        btn_clear_tables.clicked.connect(self.clear_selection)
        tbl_btns.addWidget(btn_clear_tables)
        self.btn_clear_tables = btn_clear_tables

        left_layout.addLayout(tbl_btns)

        left_panel.setLayout(left_layout)
        
        # === PAINEL CENTRAL: dividido horizontalmente em Manual (esquerda)
        # e Pré-definida (direita) ===
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        try:
            center_layout.setContentsMargins(6, 6, 6, 6)
            center_layout.setSpacing(6)
        except Exception:
            pass

        # === PAINEL CENTRAL: Manual / Pré-definida (controlado por RadioButton) ===

        # --- Manual panel ---
        manual_panel = QWidget()
        manual_layout = QVBoxLayout(manual_panel)
        try:
            manual_layout.setContentsMargins(6, 6, 6, 6)
            manual_layout.setSpacing(6)
        except Exception:
            pass

        manual_layout.addWidget(QLabel("<b>🧩 Informações disponíveis</b>"))

        self.column_search = QLineEdit()
        self.column_search.setPlaceholderText("Pesquisar informações...")
        self.column_search.setClearButtonEnabled(True)
        self.column_search.textChanged.connect(self.filter_columns)
        manual_layout.addWidget(self.column_search)

        self.columns_list = QListWidget()
        self.columns_list.setSelectionMode(QListWidget.MultiSelection)
        manual_layout.addWidget(self.columns_list)

        col_btns = QHBoxLayout()
        self.btn_select_all = QPushButton("✔️ Marcar todas")
        self.btn_select_all.clicked.connect(self.select_all_columns)
        col_btns.addWidget(self.btn_select_all)

        self.btn_deselect_all = QPushButton("✖️ Desmarcar todas")
        self.btn_deselect_all.clicked.connect(self.deselect_all_columns)
        col_btns.addWidget(self.btn_deselect_all)
        manual_layout.addLayout(col_btns)

        self.btn_add_columns = QPushButton("➕ Adicionar informações")
        self.btn_add_columns.clicked.connect(self.add_selected_columns)
        manual_layout.addWidget(self.btn_add_columns)

        manual_layout.addWidget(QLabel("<b>✅ Informações que aparecerão no relatório</b>"))
        self.selected_columns_list = QListWidget()
        manual_layout.addWidget(self.selected_columns_list)

        btn_remove_column = QPushButton("➖ Remover informação")
        btn_remove_column.clicked.connect(self.remove_selected_column)
        manual_layout.addWidget(btn_remove_column)

        manual_panel.setLayout(manual_layout)

        # --- Pré-definida panel ---
        predefined_panel = QWidget()
        self.predefined_layout = QVBoxLayout(predefined_panel)
        try:
            self.predefined_layout.setContentsMargins(6, 6, 6, 6)
            self.predefined_layout.setSpacing(6)
        except Exception:
            pass
        predefined_panel.setLayout(self.predefined_layout)

        # adiciona ambos ao centro (sem abas)
        center_layout.addWidget(predefined_panel)
        center_layout.addWidget(manual_panel)

        # estado inicial: pré-definida visível
        predefined_panel.setVisible(True)
        manual_panel.setVisible(False)

        # guarda referência para controle posterior
        self._manual_panel = manual_panel
        self._predefined_panel = predefined_panel

        center_panel.setLayout(center_layout)
        
        # === PAINEL DIREITO: Configurações e Execução ===
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        try:
            right_layout.setContentsMargins(6, 6, 6, 6)
            
            right_layout.setSpacing(6)
        except Exception:
            pass

        # Módulo / Agrupamento (Query Builder metadata)
        # Modo de consulta: metadados ou manual
        # We'll separate the small radio group from the hint/help so we can
        # force the radios to remain at the left of the top bar and the hint
        # to the right.
        mode_buttons_layout = QHBoxLayout()
        mode_label = QLabel("Modo de consulta:")
        mode_buttons_layout.addWidget(mode_label)
        self.mode_meta_radio = QRadioButton("Pré-definida")
        self.mode_manual_radio = QRadioButton("Manual")
        self.mode_meta_radio.setChecked(True)
        mode_buttons_layout.addWidget(self.mode_meta_radio)
        mode_buttons_layout.addWidget(self.mode_manual_radio)
        # Hint label para mostrar modo atual com destaque (placed on the right)
        self.mode_hint_label = QLabel("")
        self.mode_hint_label.setStyleSheet('font-weight: bold;')
        self.mode_hint_label.setContentsMargins(8, 0, 0, 0)
        # Help icon (small) with tooltip and clickable dialog (also on the right)
        self.mode_help_btn = QToolButton()
        try:
            self.mode_help_btn.setText("ℹ")
            self.mode_help_btn.setToolTip("O que significa cada modo? Clique para mais informações.")
            self.mode_help_btn.setCursor(Qt.PointingHandCursor)
            self.mode_help_btn.setStyleSheet('border: none; font-size: 14px;')
            self.mode_help_btn.clicked.connect(self.show_query_mode_help)
        except Exception:
            pass
        # backward-compatible container used by older fallbacks
        try:
            mode_layout = QHBoxLayout()
            try:
                mode_layout.addLayout(mode_buttons_layout)
                mode_layout.addStretch()
                mode_layout.addWidget(self.mode_hint_label, alignment=Qt.AlignVCenter)
                mode_layout.addWidget(self.mode_help_btn, alignment=Qt.AlignVCenter)
            except Exception:
                pass
        except Exception:
            mode_layout = None
        # mover os controles de modo (Pré-definida / Manual) para o canto superior esquerdo
        try:
            # botão expansor do painel esquerdo (indica onde clicar para expandir/minimizar)
            self.btn_expander = QToolButton()
            self.btn_expander.setText('◀')
            self.btn_expander.setToolTip('Expandir / Minimizar painel esquerdo')
            try:
                self.btn_expander.setFixedSize(22, 22)
            except Exception:
                pass
            def _toggle_left_panel():
                try:
                    vis = left_panel.isVisible()
                    left_panel.setVisible(not vis)
                    # atualizar ícone/texto do botão
                    try:
                        self.btn_expander.setText('▶' if vis else '◀')
                    except Exception:
                        pass
                except Exception:
                    pass
            try:
                self.btn_expander.clicked.connect(_toggle_left_panel)
            except Exception:
                pass

            # place the expander button on the top bar (left) so it remains
            # visible regardless of the left panel's visibility. Then place
            # the mode controls to the right of it.
            try:
                try:
                    top_bar_layout.addWidget(self.btn_expander, alignment=Qt.AlignLeft)
                except Exception:
                    top_bar_layout.addWidget(self.btn_expander)
                # NOTE: radio buttons are moved to the actions column on the
                # right (so we don't add them to the top bar). Keep the
                # fallbacks minimal here.
                # push hint/help to the right
                try:
                    top_bar_layout.addStretch()
                    top_bar_layout.addWidget(self.mode_hint_label, alignment=Qt.AlignVCenter)
                    top_bar_layout.addWidget(self.mode_help_btn, alignment=Qt.AlignVCenter)
                except Exception:
                    pass
            except Exception:
                # fallback: original behavior (insert inside left panel)
                try:
                    left_layout.insertWidget(0, self.btn_expander, alignment=Qt.AlignLeft)
                    left_layout.insertLayout(1, mode_layout)
                except Exception:
                    left_layout.insertLayout(0, mode_layout)
        except Exception:
            # fallback: manter no painel direito
            right_layout.addLayout(mode_layout)

        # conecta sinais para alternar modo
        try:
            # tooltips explicativos
            self.mode_meta_radio.setToolTip('Usar metadados JSON para gerar consultas automaticamente (recomendado).')
            self.mode_manual_radio.setToolTip('Modo manual: selecione tabelas e colunas livremente para montar sua consulta.')
            self.mode_meta_radio.toggled.connect(lambda checked: self.set_query_mode('metadados') if checked else None)
            self.mode_manual_radio.toggled.connect(lambda checked: self.set_query_mode('manual') if checked else None)
        except Exception:
            pass

        # adicionar o bloco de módulo/agrupamento no painel 'Pré-definida'
        try:
            self.predefined_layout.addWidget(QLabel("<b>🧭 Módulo / Agrupamento</b>"))
        except Exception:
            right_layout.addWidget(QLabel("<b>🧭 Módulo / Agrupamento</b>"))
        self.combo_modulo = QComboBox()
        self.combo_modulo.setToolTip("Selecione o módulo (ex.: financeiro, comercial)")
        # ensure combobox popup text is readable regardless of global styles
        try:
            # Use stylesheet-only approach (no palette manipulation)
            self.combo_modulo.setStyleSheet(
                """
QComboBox {
    color: #000000 !important;
    background-color: #ffffff !important;
}

QComboBox QAbstractItemView {
    background-color: #ffffff !important;
    color: #000000 !important;
    selection-background-color: #3874f2 !important;
    selection-color: #ffffff !important;
}

QComboBox QAbstractItemView::item {
    padding: 4px 8px !important;
    color: #000000 !important;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #dce9ff !important;
    color: #000000 !important;
    border-left: 3px solid #3874f2 !important;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #3874f2 !important;
    color: #ffffff !important;
}
"""
            )
            try:
                # Also ensure the popup view uses the same stylesheet (avoid palette issues)
                v = self.combo_modulo.view()
                v.setStyleSheet("""
QListView { background-color: #ffffff; color: #000000; }
QListView::item { padding: 4px 8px; }
QListView::item:hover { background-color: #dce9ff; color: #000000; border-left: 3px solid #3874f2; }
QListView::item:selected { background-color: #3874f2; color: #ffffff; }
""")
            except Exception:
                pass
        except Exception:
            pass
        try:
            self.predefined_layout.addWidget(self.combo_modulo)
        except Exception:
            right_layout.addWidget(self.combo_modulo)

        self.combo_agrupamento = QComboBox()
        self.combo_agrupamento.setToolTip("Selecione o agrupamento dentro do módulo")
        try:
            # Use stylesheet-only approach (no palette manipulation)
            self.combo_agrupamento.setStyleSheet(
                """
QComboBox {
    color: #000000;
    background-color: #ffffff;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #000000;
    selection-background-color: #3874f2;
    selection-color: #ffffff;
}

QComboBox QAbstractItemView::item {
    padding: 4px 8px;
    color: #000000;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #dce9ff;
    color: #000000;
    border-left: 3px solid #3874f2;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #3874f2;
    color: #ffffff;
}
"""
            )
            try:
                v = self.combo_agrupamento.view()
                v.setStyleSheet("""
QListView { background-color: #ffffff; color: #000000; }
QListView::item { padding: 4px 8px; }
QListView::item:hover { background-color: #dce9ff; color: #000000; border-left: 3px solid #3874f2; }
QListView::item:selected { background-color: #3874f2; color: #ffffff; }
""")
            except Exception:
                pass
        except Exception:
            pass
        try:
            self.predefined_layout.addWidget(self.combo_agrupamento)
        except Exception:
            right_layout.addWidget(self.combo_agrupamento)

        # conecta sinais para manter atributos e carregar agrupamentos
        try:
            self.combo_modulo.currentIndexChanged.connect(self._on_modulo_selected)
            self.combo_agrupamento.currentIndexChanged.connect(self._on_agrupamento_selected)
        except Exception:
            pass

        # popula módulos (se possível)
        try:
            md_path = getattr(self.qb, 'pasta_metadados', None)
            if md_path:
                md = Path(md_path)
                # se for caminho relativo, resolve relativo ao diretório do script
                if not md.is_absolute():
                    md = Path(os.path.dirname(__file__)) / md_path
                if md.exists() and md.is_dir():
                    modules = []
                    for p in sorted(md.glob('*.json')):
                        name = p.name
                        if name.endswith('_agrupamentos.json'):
                            continue
                        modules.append(p.stem)
                    # inserir placeholder e popular sem disparar signals automáticos
                    try:
                        self.combo_modulo.blockSignals(True)
                        self.combo_modulo.addItem("-- Selecione módulo --", None)
                        for m in modules:
                            self.combo_modulo.addItem(m, m)
                        # manter placeholder selecionado (nenhuma ação automática)
                        self.combo_modulo.setCurrentIndex(0)
                    finally:
                        try:
                            self.combo_modulo.blockSignals(False)
                        except Exception:
                            pass
        except Exception:
            pass
        
    # Cláusula WHERE
        # Adiciona a seção de filtros ao painel 'Pré-definida'
        try:
            self.predefined_layout.addWidget(QLabel("<b>🎯 Filtros</b>"))
        except Exception:
            right_layout.addWidget(QLabel("<b>🎯 Filtros</b>"))
        # Filtros rápidos (apenas no modo metadados)
        filters_box = QGroupBox("Filtros rápidos")
        filters_layout = QVBoxLayout(filters_box)

        self.combo_filter_field = QComboBox()
        self.combo_filter_field.setToolTip(
            'Escolha o campo para filtrar (carregado do agrupamento)'
        )
        self.combo_filter_field.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )
        filters_layout.addWidget(self.combo_filter_field)


#        filters_box = QGroupBox("Filtros rápidos")
#        filters_layout = QHBoxLayout()
#        self.combo_filter_field = QComboBox()
#        self.combo_filter_field.setToolTip('Escolha o campo para filtrar (carregado do agrupamento)')
        try:
            # dropdown must be readable even when hovered; force black text on items
            self.combo_filter_field.setStyleSheet(
                """
QComboBox {
    color: #000000 !important;
    background-color: #ffffff !important;
}

QComboBox QAbstractItemView {
    background-color: #ffffff !important;
    color: #000000 !important;
    selection-background-color: #3874f2 !important;
    selection-color: #ffffff !important;
}

QComboBox QAbstractItemView::item {
    padding: 4px 8px !important;
    color: #000000 !important;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #dce9ff !important;
    color: #000000 !important;
    border-left: 3px solid #3874f2 !important;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #3874f2 !important;
    color: #ffffff !important;
}
"""
            )
            try:
                v = self.combo_filter_field.view()
                v.setStyleSheet("""
QListView { background-color: #ffffff; color: #000000; }
QListView::item { padding: 4px 8px; }
QListView::item:hover { background-color: #dce9ff; color: #000000; border-left: 3px solid #3874f2; }
QListView::item:selected { background-color: #3874f2; color: #ffffff; }
""")
            except Exception:
                pass
        except Exception:
            pass
        # initial state: no module/agrupamento selected -> disable filter field
        try:
            self.combo_filter_field.addItem("-- selecione módulo e agrupamento --", None)
            self.combo_filter_field.setEnabled(False)
        except Exception:
            pass
        filters_layout.addWidget(self.combo_filter_field)

        self.combo_filter_op = QComboBox()
        self.combo_filter_op.addItems(["=", "!=", ">", "<", ">=", "<=", "BETWEEN", "IN", "LIKE"])
        self.combo_filter_op.setFixedWidth(90)
        filters_layout.addWidget(self.combo_filter_op)

        # Valor - suportamos 3 tipos de widget e alternamos visibilidade conforme o tipo do campo
        # 1) Texto livre (QLineEdit)
        self.filter_value_input = QLineEdit()
        self.filter_value_input.setPlaceholderText("Valor (ou lista separada por , para IN)")
        filters_layout.addWidget(self.filter_value_input)
        # campo "to" para BETWEEN em texto (visível somente quando necessário)
        self.filter_value_input_to = QLineEdit()
        self.filter_value_input_to.setPlaceholderText("Valor 2 (usado em BETWEEN)")
        self.filter_value_input_to.setVisible(False)
        filters_layout.addWidget(self.filter_value_input_to)

        # 2) Datas (QDateEdit)
        self.filter_date1 = QDateEdit()
        self.filter_date1.setCalendarPopup(True)
        self.filter_date1.setDisplayFormat('MM-dd-yyyy')
        try:
            self.filter_date1.setDate(QDate.currentDate())
        except Exception:
            pass
        self.filter_date1.setVisible(False)
        filters_layout.addWidget(self.filter_date1)

        self.filter_date2 = QDateEdit()
        self.filter_date2.setCalendarPopup(True)
        self.filter_date2.setDisplayFormat('MM-dd-yyyy')
        try:
            self.filter_date2.setDate(QDate.currentDate())
        except Exception:
            pass
        self.filter_date2.setVisible(False)
        filters_layout.addWidget(self.filter_date2)

        # 3) Numéricos (QDoubleSpinBox)
        self.filter_num1 = QDoubleSpinBox()
        self.filter_num1.setRange(-1e12, 1e12)
        self.filter_num1.setDecimals(4)
        self.filter_num1.setVisible(False)
        filters_layout.addWidget(self.filter_num1)

        self.filter_num2 = QDoubleSpinBox()
        self.filter_num2.setRange(-1e12, 1e12)
        self.filter_num2.setDecimals(4)
        self.filter_num2.setVisible(False)
        filters_layout.addWidget(self.filter_num2)
        # Connector selector (AND/OR) for panel-based filter creation
        self.filter_connector_combo = QComboBox()
        self.filter_connector_combo.addItems(["AND", "OR"])
        self.filter_connector_combo.setFixedWidth(80)
        filters_layout.addWidget(self.filter_connector_combo)

        self.btn_add_filter = QPushButton("Adicionar filtro")
        self.btn_add_filter.clicked.connect(self._on_add_filter_clicked)
        self.btn_add_filter.setMinimumWidth(120)
        filters_layout.addWidget(self.btn_add_filter)

        # conectar mudanças para alternar widgets conforme seleção
        try:
            self.combo_filter_field.currentIndexChanged.connect(self._on_filter_field_changed)
            self.combo_filter_op.currentTextChanged.connect(self._on_filter_op_changed)
        except Exception:
            pass

        filters_box.setLayout(filters_layout)
        try:
            self.predefined_layout.addWidget(filters_box)
        except Exception:
            right_layout.addWidget(filters_box)

        # Gerenciador de filtros parametrizados (lista + remover/limpar)
        manage_box = QGroupBox("Gerenciar filtros")
        manage_layout = QVBoxLayout(manage_box)
        try:
            # garantir espaço entre o título do QGroupBox e o conteúdo
            manage_layout.setContentsMargins(8, 22, 8, 8)
            manage_layout.setSpacing(6)
        except Exception:
            pass

        self.filters_list = QListWidget()
        self.filters_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.filters_list.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )
        try:
            # garantir altura mínima e máxima para evitar que a lista ocupe
            # todo o espaço e empurre os botões para fora em telas baixas
            # em notebooks 1366x768 uma altura máxima de ~180 deixa espaço
            # para os botões abaixo; ajustável se necessário.
            self.filters_list.setMinimumHeight(80)
            self.filters_list.setMaximumHeight(180)
            # garantir barra de rolagem vertical quando necessário
            try:
                self.filters_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            except Exception:
                pass
        except Exception:
            pass
        manage_layout.addWidget(self.filters_list)

        # === Botões em layout vertical (evita sobreposição em telas menores) ===
        btn_layout = QVBoxLayout()

        def _cfg_btn(btn):
            btn.setMinimumHeight(34)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.btn_remove_filter = QPushButton("➖ Remover filtro selecionado")
        self.btn_remove_filter.clicked.connect(self._remove_selected_filter)
        _cfg_btn(self.btn_remove_filter)
        btn_layout.addWidget(self.btn_remove_filter)

        self.btn_clear_filters = QPushButton("🧹 Limpar filtros")
        self.btn_clear_filters.clicked.connect(self._clear_param_filters)
        _cfg_btn(self.btn_clear_filters)
        btn_layout.addWidget(self.btn_clear_filters)

        # botão editar filtro
        self.btn_edit_filter = QPushButton("✏️ Editar filtro")
        self.btn_edit_filter.clicked.connect(self._edit_selected_filter)
        _cfg_btn(self.btn_edit_filter)
        btn_layout.addWidget(self.btn_edit_filter)

        # botão desfazer (restaura where_input anterior à sincronização)
        self.btn_undo_where = QPushButton("↶ Desfazer WHERE")
        self.btn_undo_where.setEnabled(False)
        self.btn_undo_where.clicked.connect(self._undo_last_where)
        _cfg_btn(self.btn_undo_where)
        btn_layout.addWidget(self.btn_undo_where)

        # botão refazer
        self.btn_redo_where = QPushButton("↷ Refazer WHERE")
        self.btn_redo_where.setEnabled(False)
        self.btn_redo_where.clicked.connect(self._redo_last_where)
        _cfg_btn(self.btn_redo_where)
        btn_layout.addWidget(self.btn_redo_where)

        # colocar os botões em um widget container para garantir que
        # ocupem espaço fixo na parte inferior do grupo e possam ser
        # visualizados mesmo quando a lista de filtros for rolada.
        try:
            # usar QScrollArea para o conjunto de botões: mantém botões
            # com tamanho normal e adiciona barra de rolagem quando necessário
            btn_container_scroll = QScrollArea()
            btn_container_scroll.setWidgetResizable(True)
            btn_inner = QWidget()
            btn_inner.setLayout(btn_layout)
            btn_container_scroll.setWidget(btn_inner)
            try:
                btn_container_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                btn_container_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            except Exception:
                pass
            try:
                # limitar altura do scroll area para que ele não ocupe todo o grupo
                btn_container_scroll.setMaximumHeight(200)
            except Exception:
                pass
            manage_layout.addWidget(btn_container_scroll)
        except Exception:
            # fallback: adiciona o layout diretamente
            manage_layout.addLayout(btn_layout)


        # WHERE input (mover para dentro do grupo Gerenciar filtros para evitar duplicação)
        self.where_input = QTextEdit()
        self.where_input.setPlaceholderText("Ex: DataVenda >= '2024-01-01'")
        self.where_input.setMaximumHeight(100)
        # NOTE: we keep `where_input` as an internal buffer but do NOT add it to the
        # layout -- all filters (manual or metadados) should appear only in the
        # `self.filters_list` (Gerenciar filtros). Hiding the widget prevents the
        # duplicate field below the buttons while preserving existing code that
        # reads/writes `self.where_input` internally.
        try:
            self.where_input.setVisible(False)
        except Exception:
            pass

        manage_box.setLayout(manage_layout)
        try:
            self.predefined_layout.addWidget(manage_box)
        except Exception:
            right_layout.addWidget(manage_box)

        # SQL Gerada - colocar abaixo do gerenciador de filtros (manage_box)
        try:
            self.predefined_layout.addWidget(QLabel("<b>🧠 Consulta criada automaticamente</b>"))
            self.sql_preview = QTextEdit()
            self.sql_preview.setReadOnly(True)
            self.sql_preview.setMaximumHeight(150)
            self.predefined_layout.addWidget(self.sql_preview)
        except Exception:
            # fallback para painel direito (se predefined_layout não aceitar)
            right_layout.addWidget(QLabel("<b>🧠 Consulta criada automaticamente</b>"))
            self.sql_preview = QTextEdit()
            self.sql_preview.setReadOnly(True)
            self.sql_preview.setMaximumHeight(150)
            right_layout.addWidget(self.sql_preview)

        # badge que aparece quando a SQL for regenerada automaticamente
        try:
            self.auto_update_badge = QLabel("Atualizada")
            self.auto_update_badge.setVisible(False)
            self.auto_update_badge.setStyleSheet(
                "background:#ffd54f; color:#333; padding:4px 8px; border-radius:10px; font-size:11px;"
            )
            try:
                self.predefined_layout.addWidget(self.auto_update_badge)
            except Exception:
                right_layout.addWidget(self.auto_update_badge)
        except Exception:
            self.auto_update_badge = None

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
        btn_generate.setMinimumWidth(140)
        btn_generate.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        action_layout.addWidget(btn_generate)

        btn_execute = QPushButton("▶️ Executar consulta")
        btn_execute.clicked.connect(self.execute_query)
        btn_execute.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        btn_execute.setMinimumWidth(140)
        btn_execute.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        action_layout.addWidget(btn_execute)

        btn_save = QPushButton("💾 Salvar consulta")
        btn_save.clicked.connect(self.save_query)
        btn_save.setMinimumWidth(140)
        btn_save.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        action_layout.addWidget(btn_save)

        btn_load = QPushButton("📂 Carregar consulta")
        btn_load.clicked.connect(self.load_query)
        btn_load.setMinimumWidth(140)
        btn_load.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        action_layout.addWidget(btn_load)

        btn_delete = QPushButton("🗑️ Excluir consulta")
        btn_delete.clicked.connect(self.delete_query)
        btn_delete.setMinimumWidth(140)
        btn_delete.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        action_layout.addWidget(btn_delete)

        btn_manage = QPushButton("🔧 Gerenciar consultas")
        # Abrir o gerenciador de consultas da janela principal (MainWindow)
        btn_manage.clicked.connect(lambda: (self.window().open_manage_queries() if hasattr(self.window(), 'open_manage_queries') else None))
        btn_manage.setMinimumWidth(140)
        btn_manage.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        action_layout.addWidget(btn_manage)

        right_layout.addStretch()
        right_panel.setLayout(right_layout)
        
        # === SPLITTER PARA REDIMENSIONAMENTO ===
        # painel de ações (botões verticais à direita)
        actions_panel = QWidget()
        actions_layout = QVBoxLayout(actions_panel)
        try:
            actions_layout.setContentsMargins(6,4,6,6)
            actions_layout.setSpacing(6)
            actions_layout.setAlignment(Qt.AlignTop)
        except Exception:
            pass
        # transferir os botões criados acima para este layout (eles já existem)
        try:
            actions_layout.addWidget(btn_generate)
            actions_layout.addWidget(btn_execute)
            actions_layout.addWidget(btn_save)
            actions_layout.addWidget(btn_load)
            actions_layout.addWidget(btn_delete)
            actions_layout.addWidget(btn_manage)
        except Exception:
            pass
        # Ajustes visuais: largura/altura consistentes para formar botões retangulares
        try:
            for b in (btn_generate, btn_execute, btn_save, btn_load, btn_delete, btn_manage):
                try:
                    b.setMinimumWidth(150)
                    b.setFixedHeight(36)
                    b.setStyleSheet("border-radius:4px; text-align:left; padding-left:8px;")
                except Exception:
                    pass
        except Exception:
            pass
        # estilo simples: largura fixa para manter forma retangular
        # largura configurável pelo usuário (persistida em user_prefs.json)
        actions_panel.setLayout(actions_layout)
        try:
            pref_w = int(self._load_user_pref('actions_panel_width', 180))
        except Exception:
            pref_w = 180
        actions_panel.setFixedWidth(pref_w)

        # spinbox para ajustar largura dinamicamente
        try:
            width_ctrl_layout = QHBoxLayout()
            width_ctrl_layout.setContentsMargins(0,0,0,6)
            lbl_w = QLabel('Largura painel:')
            spin_w = QSpinBox()
            spin_w.setRange(100, 600)
            spin_w.setValue(pref_w)
            spin_w.setSingleStep(10)
            def _on_width_changed(v):
                try:
                    actions_panel.setFixedWidth(v)
                    self._save_user_pref('actions_panel_width', int(v))
                except Exception:
                    pass
            spin_w.valueChanged.connect(_on_width_changed)
            width_ctrl_layout.addWidget(lbl_w)
            width_ctrl_layout.addWidget(spin_w)
            # inserir no topo do actions_layout
            actions_layout.insertLayout(0, width_ctrl_layout)
        except Exception:
            pass

        # Inserir os rádios de modo na coluna de ações (antes dos botões)
        try:
            mode_widget = QWidget()
            mv = QVBoxLayout(mode_widget)
            mv.setContentsMargins(0, 0, 0, 6)
            mv.setSpacing(4)
            # ordem solicitada: primeiro Pré-definida, abaixo Manual
            try:
                mv.addWidget(self.mode_meta_radio)
                mv.addWidget(self.mode_manual_radio)
            except Exception:
                pass
            # inserir logo abaixo do controle de largura (índice 1)
            try:
                # insert with top-left alignment so radios appear close to top
                actions_layout.insertWidget(1, mode_widget, alignment=Qt.AlignTop | Qt.AlignLeft)
            except Exception:
                try:
                    actions_layout.addWidget(mode_widget, alignment=Qt.AlignTop | Qt.AlignLeft)
                except Exception:
                    pass
        except Exception:
            pass

        # ensure content stays compact at the top by adding a stretch at the end
        try:
            actions_layout.addStretch()
        except Exception:
            pass

        splitter = QSplitter(Qt.Horizontal)
        # NOTE: expander button is now in the top_bar; no need to add a
        # separate expander container to the splitter.
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.addWidget(actions_panel)
        # stretch factors: expander(0) - left(1) - center(2) - right(2) - actions(0)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)
        splitter.setStretchFactor(3, 2)
        splitter.setStretchFactor(4, 0)
        
        # adicionar a barra superior (contendo os rádios de modo) acima do splitter
        try:
            layout.addWidget(top_bar)
        except Exception:
            pass
        layout.addWidget(splitter)
        self.setLayout(layout)
        # Por padrão, definir modo 'metadados' (bloqueia controles manuais)
        try:
            self.set_query_mode('metadados')
        except Exception:
            pass

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
        # inicializa limites dinâmicos para lista de filtros
        try:
            # call once to set sensible maximum based on current widget size
            self._update_filters_list_max_height()
        except Exception:
            pass
    
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

    def _update_filters_list_max_height(self):
        """Calcula e aplica uma altura máxima para `self.filters_list` com base
        na altura atual do widget, evitando que a lista ocupe todo o espaço
        e esconda os botões em telas com pouca altura.
        """
        try:
            # se o widget ainda não existir, nada a fazer
            if not getattr(self, 'filters_list', None):
                return
            total_h = self.height() if hasattr(self, 'height') else 600
            # reservar uma fração da altura para a lista (ex: 35-45%)
            max_h = int(total_h * 0.42)
            if max_h < 80:
                max_h = 80
            if max_h > 400:
                max_h = 400
            try:
                self.filters_list.setMaximumHeight(max_h)
            except Exception:
                pass
        except Exception:
            pass

    def resizeEvent(self, event):
        # atualiza limite da lista de filtros ao redimensionar
        try:
            try:
                super().resizeEvent(event)
            except Exception:
                pass
            try:
                self._update_filters_list_max_height()
            except Exception:
                pass
        except Exception:
            pass

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

    def _load_user_pref(self, key: str, default=None):
        """Carrega preferência simples do arquivo user_prefs.json ao lado do script."""
        try:
            p = os.path.join(os.path.dirname(__file__), 'user_prefs.json')
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get(key, default)
        except Exception:
            pass
        return default

    def _save_user_pref(self, key: str, value):
        try:
            p = os.path.join(os.path.dirname(__file__), 'user_prefs.json')
            data = {}
            if os.path.exists(p):
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        data = json.load(f) or {}
                except Exception:
                    data = {}
            data[key] = value
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

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
                # se já existe ao menos uma tabela, solicitar tipo de JOIN ao usuário
                join_type = None
                try:
                    if self.selected_tables_list.count() >= 1:
                        from PyQt5.QtWidgets import QInputDialog
                        options = ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN"]
                        choice, ok = QInputDialog.getItem(self, "Tipo de relacionamento", f"Escolha o tipo de JOIN para {raw}:", options, 0, False)
                        if not ok:
                            # usuário cancelou escolha -> pular esta tabela
                            continue
                        join_type = choice
                except Exception:
                    join_type = None

                idx = self.selected_tables_list.count() + 1
                display = f"{idx}: {raw}"
                if join_type:
                    display = f"{idx}: {raw} [{join_type}]"
                li = QListWidgetItem(display)
                li.setData(Qt.UserRole, raw)
                # armazenar join_type em role adicional
                try:
                    li.setData(Qt.UserRole + 1, join_type)
                except Exception:
                    pass
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
        # limpa filtros param
        self._param_filters = []
        try:
            self._refresh_filters_list()
        except Exception:
            pass
    
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

    def _make_aliases_for_tables(self, tables: list) -> dict:
        """Gera um mapa (schema,table) -> alias para uma lista de tuplas (schema,table).

        Reutiliza a mesma heurística usada por `_compute_aliases_for_selected_tables`.
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

        style = self.alias_style_combo.currentText() if hasattr(self, 'alias_style_combo') else 'Curto (apg,cli)'
        maker = make_alias_short if style.lower().startswith('curto') else make_alias_desc

        for schema, table_name in tables:
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
            # join type may be stored in UserRole+1
            try:
                join_type = item.data(Qt.UserRole + 1)
            except Exception:
                join_type = None
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
            if join_type:
                display = f"{display} [{join_type}]"
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
                # adiciona ao final; se já houver tabela, solicitar tipo de JOIN
                join_type = None
                try:
                    if self.selected_tables_list.count() >= 1:
                        from PyQt5.QtWidgets import QInputDialog
                        options = ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN"]
                        choice, ok = QInputDialog.getItem(self, "Tipo de relacionamento", f"Escolha o tipo de JOIN para {raw}:", options, 0, False)
                        if not ok:
                            # usuário cancelou -> não adicionar
                            return
                        join_type = choice
                except Exception:
                    join_type = None

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
                if join_type:
                    display = f"{display} [{join_type}]"
                li = QListWidgetItem(display)
                li.setData(Qt.UserRole, raw)
                try:
                    li.setData(Qt.UserRole + 1, join_type)
                except Exception:
                    pass
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
                dt = _dt.datetime.strptime(v, f)
                return f"{dt.month}-{dt.day}-{dt.year}"
            except Exception:
                continue
        # try ISO with optional timezone (including 'Z')
        try:
            vv = v
            if vv.endswith('Z') or vv.endswith('z'):
                vv = vv[:-1] + '+00:00'
            dt = _dt.datetime.fromisoformat(vv)
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

    def _date_to_iso(self, value: str) -> str:
        """Tenta converter uma string de data para 'YYYY-MM-DD' (ISO date) para uso em parâmetros."""
        v = (value or '').strip()
        if not v:
            return v
        # try dateutil first
        try:
            from dateutil import parser as dateparser
            dt = dateparser.parse(v)
            return dt.date().isoformat()
        except Exception:
            pass

        # try fromisoformat variants
        try:
            vv = v
            if vv.endswith('Z') or vv.endswith('z'):
                vv = vv[:-1] + '+00:00'
            dt = _dt.datetime.fromisoformat(vv)
            return dt.date().isoformat()
        except Exception:
            pass

        # fallback to heuristic parsing used in normalize_date but return ISO
        fmts = [
            '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y', '%m-%d-%Y',
            '%d.%m.%Y', '%Y/%m/%d', '%Y.%m.%d',
            '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M',
        ]
        for f in fmts:
            try:
                dt = _dt.datetime.strptime(v, f)
                return dt.date().isoformat()
            except Exception:
                continue

        # last resort: try splitting
        for sep in ('-', '/', '.'):
            parts = v.split(sep)
            if len(parts) == 3:
                try:
                    p0 = int(parts[0]); p1 = int(parts[1]); p2 = int(parts[2])
                    if p0 > 31:
                        year = p0; month = p1; day = p2
                    elif p2 > 31:
                        year = p2; month = p0; day = p1
                    else:
                        month = p0; day = p1; year = p2
                    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
                except Exception:
                    continue

        # give up, return original
        return v

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
                # secondary numeric formatter used elsewhere (defined once to avoid nested def issues)
                def format_number_str2(s: str) -> str:
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
                            parts = [format_number_str2(p) for p in parts]
                        # else left as-is
                    expr = f"{field_ref} IN ({', '.join(parts)})"
                elif op == "BETWEEN":
                    if needs_date:
                        a = f"'{self.normalize_date(v1)}'"
                        b = f"'{self.normalize_date(v2)}'"
                    elif needs_number:
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
                        v = format_number_str2(v1)
                    elif needs_text:
                        v = f"'{v1}'"
                    else:
                        v = f"'{v1}'"
                    expr = f"{field_ref} {op} {v}"

                # Instead of inserting into the (now-hidden) where_input field,
                # add the expression to the parametrized filters list so it
                # appears under "Gerenciar filtros" together with metadados
                # filters. We don't currently preserve the per-item connector
                # chosen in the dialog; filters are combined with AND when
                # previewed/executed.
                try:
                    if not hasattr(self, '_param_filters') or self._param_filters is None:
                        self._param_filters = []
                    # store as (expr, params, meta, connector)
                    connector = connector_combo.currentText() if 'connector_combo' in locals() else 'AND'
                    self._param_filters.append((expr, [], None, connector))
                except Exception:
                    pass
                try:
                    self._refresh_filters_list()
                    # focus and select the newly added item so user sees it immediately
                    try:
                        self.filters_list.setFocus()
                        last_row = max(0, self.filters_list.count() - 1)
                        self.filters_list.setCurrentRow(last_row)
                        item = self.filters_list.currentItem()
                        if item:
                            self.filters_list.scrollToItem(item)
                    except Exception:
                        pass
                except Exception:
                    pass
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
        """Dispatcher: gera SQL conforme o modo selecionado.

        Comportamento:
        - Se `self.modo_consulta == 'metadados'` (padrão), delega para
          `generate_sql_metadados()` que usa o QueryBuilder.
        - Se `self.modo_consulta == 'manual'`, delega para
          `generate_sql_manual()` que monta a SQL a partir das tabelas/colunas
          selecionadas na aba (fluxo manual).

        Importante: não misturar os dois fluxos na mesma função.
        """
        modo = getattr(self, 'modo_consulta', 'metadados')
        if modo == 'manual':
            return self.generate_sql_manual()
        else:
            return self.generate_sql_metadados()

    def generate_sql_metadados(self):
        """Gera a SQL baseada nos metadados (JSON) usando QueryBuilder."""
        try:
            # Valida módulo
            if not getattr(self, "current_modulo", None):
                QMessageBox.warning(self, "Aviso", "Selecione um módulo")
                return

            # Valida agrupamento
            if not getattr(self, "current_agrupamento_id", None):
                QMessageBox.warning(self, "Aviso", "Selecione um agrupamento")
                return

            # WHERE clause (opcional)
            # Preferir filtros parametrizados adicionados via UI
            filtros = None
            where_clause = ''
            if getattr(self, '_param_filters', None):
                # normalize to tuples (expr, params) because we may store meta as third element
                filtros = []
                for f in list(self._param_filters):
                    if isinstance(f, (list, tuple)):
                        # take only expr and params if present
                        if len(f) >= 2:
                            filtros.append((f[0], f[1]))
                        elif len(f) == 1:
                            filtros.append((f[0], []))
                    else:
                        filtros.append(str(f))
            else:
                where_clause = self.where_input.toPlainText().strip()
                if where_clause:
                    filtros = [where_clause]

            # Gera SQL via QueryBuilder (metadados) — usa o QueryBuilder já injetado na aba
            qb = self.qb

            # tenta construir aliases para as tabelas referenciadas no agrupamento
            aliases = {}
            try:
                agrup_meta = self.qb.carregar_agrupamentos(self.current_modulo)
                agrup = next((a for a in agrup_meta.get('agrupamentos', []) if a.get('id') == self.current_agrupamento_id), None)
                tables = []
                if agrup:
                    # principal
                    t0 = agrup.get('tabela')
                    if t0:
                        tables.append(t0)
                    # joins
                    for j in agrup.get('joins', []):
                        jt = j.get('tabela')
                        if jt:
                            tables.append(jt)
                # parse tables into (schema, table)
                parsed = []
                for t in tables:
                    try:
                        parts = re.split(r"\.|\[|\]", t)
                        parts = [p for p in parts if p]
                        if len(parts) == 1:
                            parsed.append(('dbo', parts[0]))
                        elif len(parts) == 2:
                            parsed.append((parts[0], parts[1]))
                        else:
                            parsed.append((parts[-2], parts[-1]))
                    except Exception:
                        continue
                # build alias map
                aliases = self._make_aliases_for_tables(parsed)
            except Exception:
                aliases = {}

            # --- Auto-qualify simple column references in textual WHERE clauses ---
            def _replace_unquoted(s: str, pattern, repl):
                """Substitui ocorrências de pattern por repl fora de literais entre aspas simples.
                pattern deve ser um compiled regex."""
                out = []
                i = 0
                L = len(s)
                while i < L:
                    if s[i] == "'":
                        # copy quoted literal as-is, handle doubled single-quote escape
                        j = i + 1
                        while j < L:
                            if s[j] == "'":
                                if j+1 < L and s[j+1] == "'":
                                    # escaped quote, skip both
                                    j += 2
                                    continue
                                else:
                                    j += 1
                                    break
                            j += 1
                        out.append(s[i:j])
                        i = j
                    else:
                        # find next quote or end
                        j = s.find("'", i)
                        segment = s[i:j] if j != -1 else s[i:]
                        # apply replacement on this segment
                        segment = pattern.sub(repl, segment)
                        out.append(segment)
                        if j == -1:
                            break
                        i = j
                return ''.join(out)

            def _qualify_where_text(text: str, main_alias: Optional[str], columns: List[str]) -> str:
                """Qualifica ocorrências simples de nomes de coluna em `text` usando `main_alias`.
                Não altera referências já qualificadas (contendo '.') e preserva literais.
                """
                if not text or not main_alias or not columns:
                    return text
                # compile a regex that matches any of the column names as whole words
                # but not when preceded by a dot (i.e., already qualified)
                cols_sorted = sorted(columns, key=lambda x: -len(x))
                # escape for regex
                pat = r"\b(" + '|'.join(re.escape(c) for c in cols_sorted) + r")\b"
                compiled = re.compile(pat, re.IGNORECASE)

                def repl(m):
                    start = m.start()
                    # check previous char in the segment (we are in a segment without quotes)
                    # if previous char is '.' then skip replacement (already qualified)
                    # can't access absolute position here easily, so rely on lookbehind: ensure not preceded by '.'
                    # use a simple check on the match string
                    return f"{main_alias}.{m.group(1)}"

                # use _replace_unquoted to avoid changing literals
                return _replace_unquoted(text, compiled, repl)

            # if we have a textual where_clause (not parametrized) try to qualify
            try:
                # get main table and alias
                main_table = None
                if agrup:
                    main_table = agrup.get('tabela')
                main_alias = None
                if main_table:
                    parts = re.split(r"\.|\[|\]", main_table)
                    parts = [p for p in parts if p]
                    if len(parts) == 1:
                        main_schema, main_tbl = 'dbo', parts[0]
                    elif len(parts) == 2:
                        main_schema, main_tbl = parts[0], parts[1]
                    else:
                        main_schema, main_tbl = parts[-2], parts[-1]
                    if aliases and (main_schema, main_tbl) in aliases:
                        main_alias = aliases[(main_schema, main_tbl)]

                # collect candidate column names from agrupamento (dimensoes + metricas)
                candidate_cols = []
                if agrup:
                    for d in agrup.get('dimensoes', []):
                        if isinstance(d, dict):
                            fld = d.get('campo')
                        else:
                            fld = d
                        if isinstance(fld, str) and fld:
                            # strip possible qualification
                            candidate_cols.append(fld.split('.')[-1].strip('[]'))
                    for m in agrup.get('metricas', []):
                        fld = m.get('campo') if isinstance(m, dict) else m
                        if isinstance(fld, str) and fld:
                            candidate_cols.append(fld.split('.')[-1].strip('[]'))

                # apply qualification to where_clause and to filtros entries that are plain strings
                if where_clause:
                    new_where = _qualify_where_text(where_clause, main_alias, candidate_cols)
                    if new_where != where_clause:
                        where_clause = new_where
                        filtros = [where_clause]
                if filtros and isinstance(filtros, list):
                    new_filters = []
                    modified = False
                    for it in filtros:
                        if isinstance(it, str):
                            new = _qualify_where_text(it, main_alias, candidate_cols)
                            new_filters.append(new)
                            if new != it:
                                modified = True
                        else:
                            new_filters.append(it)
                    if modified:
                        filtros = new_filters
            except Exception:
                # não bloquear geração por falha nesta heurística
                pass

            # --------------------------------------------------
            # Regra de segurança: se o agrupamento contém campos de
            # data sensíveis, exigir que o usuário forneça um filtro
            # para pelo menos um desses campos antes de gerar a SQL.
            # --------------------------------------------------
            try:
                # lista de identificadores de campos de data (normalizados)
                date_fields = [
                    'dataemissao','dataentrada','datasaida','datamovimento','datavenda',
                    'datavencimento','dataprevista','dataabertura','databaixa','datacompensacao',
                    'datacompetencia','datacompra','datafaturamento','datalancamento','datapagamento',
                    'datapedido','dataprevisao','datarecebimento'
                ]

                def _norm(s: str) -> str:
                    if not s:
                        return ''
                    return re.sub(r"[^0-9a-z]", "", str(s).lower())

                # coleta campos presentes no agrupamento (dimensoes e metricas)
                agrup = agrup if 'agrup' in locals() and agrup is not None else None
                if agrup is None:
                    agrup = None
                agrup_fields = []
                if agrup:
                    for d in agrup.get('dimensoes', []):
                        if isinstance(d, dict):
                            campo = d.get('campo')
                        else:
                            campo = d
                        if campo:
                            agrup_fields.append(str(campo))
                    for m in agrup.get('metricas', []):
                        campo = m.get('campo')
                        if campo:
                            agrup_fields.append(str(campo))

                # normaliza e identifica quais campos de data estão presentes
                agrup_norm = { _norm(f): f for f in agrup_fields }
                present_date_keys = [k for k in date_fields if k in agrup_norm]

                if present_date_keys:
                    # construir lista de expressões de filtro atualmente definidas
                    exprs = []
                    if filtros:
                        for f in filtros:
                            if isinstance(f, (list, tuple)) and len(f) >= 1:
                                exprs.append(str(f[0]))
                            else:
                                exprs.append(str(f))
                    wc = where_clause or ''
                    if wc:
                        exprs.append(wc)

                    # verificar se ao menos um dos campos de data possui filtro
                    ok = False
                    missing_friendly = []
                    # para detectar mesmo quando existe alias/table qualifier, usamos regex
                    for key in present_date_keys:
                        original_field = agrup_norm.get(key, key)
                        try:
                            pat = re.compile(r"\b" + re.escape(original_field) + r"\b", re.IGNORECASE)
                        except Exception:
                            pat = None

                        found = False
                        if pat:
                            for e in exprs:
                                try:
                                    if pat.search(e):
                                        found = True
                                        break
                                except Exception:
                                    continue

                        if found:
                            ok = True
                            break
                        else:
                            # coletar nome amigável para mensagem
                            friendly = None
                            try:
                                friendly = get_field_label(self.current_modulo, original_field)
                            except Exception:
                                friendly = None
                            if not friendly:
                                try:
                                    friendly = self._prettify_field_label(original_field)
                                except Exception:
                                    friendly = original_field
                            missing_friendly.append(friendly)

                    if not ok:
                        # mensagem para o usuário (lista amigável única)
                        missing_list = ', '.join(sorted(set(missing_friendly)))
                        QMessageBox.warning(
                            self,
                            'Filtro de data necessário',
                            f"Este agrupamento contém campos de data ({missing_list}).\n" +
                            "Para gerar a consulta você deve informar um filtro para a(s) data(s) referente(s) ao módulo selecionado."
                        )
                        return
            except Exception:
                # em caso de erro na verificação, não bloquear a geração — apenas registrar em debug
                try:
                    if getattr(self, '_debug_filter_populate', False):
                        print('[DEBUG] Falha ao verificar filtros de data obrigatórios')
                except Exception:
                    pass

            sql, sql_params = qb.gerar_sql_por_agrupamento(
                modulo=self.current_modulo,
                agrupamento_id=self.current_agrupamento_id,
                filtros=filtros,
                aliases=aliases
            )

            # Preview do SQL
            preview = sql
            # Se houver parâmetros, substituir '?' por valores legíveis no preview
            try:
                if sql_params:
                    psql = preview
                    for p in sql_params:
                        # formatar valor para SQL literal no preview
                        if p is None:
                            sval = 'NULL'
                        elif isinstance(p, (_dt.date, _dt.datetime)):
                            try:
                                sval = f"'{p.strftime('%m-%d-%Y')}'"
                            except Exception:
                                sval = f"'{str(p)}'"
                        elif isinstance(p, str):
                            # tenta interpretar como ISO date e reformatar para MM-DD-YYYY
                            try:
                                dt = _dt.datetime.fromisoformat(p)
                                sval = f"'{dt.strftime('%m-%d-%Y')}'"
                            except Exception:
                                m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', p)
                                if m:
                                    sval = f"'{m.group(2)}-{m.group(3)}-{m.group(1)}'"
                                else:
                                    sval = f"'{p}'"
                        else:
                            sval = str(p)
                        psql = psql.replace('?', sval, 1)
                    preview = psql
            except Exception:
                pass

            # se não houver filtros (nem parametrizados nem expressão na textbox), indicar
            if not filtros:
                preview += "\n-- Sem filtros aplicados"

            self.sql_preview.setPlainText(preview)

            # Guarda SQL atual para execução posterior
            self.current_sql = sql
            self.current_sql_params = sql_params

            # Log de sessão (se existir)
            try:
                if getattr(self, 'session_logger', None):
                    self.session_logger.log(
                        'generate_sql',
                        'Gerou preview de SQL (metadados)',
                        {
                            'modulo': self.current_modulo,
                            'agrupamento': self.current_agrupamento_id,
                            'preview': (sql[:200] if isinstance(sql, str) else str(sql)[:200])
                        }
                    )
            except Exception:
                pass

        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro ao gerar SQL",
                f"Erro ao gerar SQL:\n{str(e)}"
            )

    def generate_sql_manual(self):
        """Gera a SQL no modo manual a partir das tabelas/colunas selecionadas.

        Esta função monta uma SQL simples. Para fluxos mais avançados (joins
        automáticos, aliases, etc.) expanda conforme necessidade.
        """
        try:

            # Coleta colunas selecionadas
            cols = [self.selected_columns_list.item(i).text() for i in range(self.selected_columns_list.count())]

            # Coleta tabelas selecionadas (raw como '[schema].TableName')
            tables_raw = [self._get_selected_table_raw_text(self.selected_tables_list.item(i)) for i in range(self.selected_tables_list.count())]
            if not tables_raw:
                QMessageBox.warning(self, "Aviso", "Selecione ao menos uma fonte (tabela) para o modo manual")
                return

            # Compute aliases for selected tables and build FROM clause with aliases
            aliases = self._compute_aliases_for_selected_tables()

            from_parts = []
            # also build a small lookup for table names -> (schema, table)
            selected_tables = []
            for t in tables_raw:
                parts = t.split('.')
                schema = parts[0].strip('[]')
                table_name = parts[1].split('(')[0].strip()
                alias = aliases.get((schema, table_name))
                selected_tables.append((schema, table_name))
                if alias:
                    from_parts.append(f"[{schema}].[{table_name}] AS {alias}")
                else:
                    from_parts.append(f"[{schema}].[{table_name}]")
            from_clause = ', '.join(from_parts)

            # Helper para resolver um campo (ex: 'table.col' ou '[schema].[table].[col]') para usar alias
            def _resolve_field_to_alias(field_text: str):
                # tenta formatos: [schema].[table].[col], schema.table.col, table.col
                try:
                    # remove espaços desnecessários
                    ft = field_text.strip()
                    # bracketed parts
                    m = re.match(r"^(?:\[?([A-Za-z0-9_]+)\]?\.)?(?:\[?([A-Za-z0-9_]+)\]?\.)?\[?([A-Za-z0-9_]+)\]?$")
                    if m:
                        # groups: maybe schema, maybe table, column
                        g1 = m.group(1)
                        g2 = m.group(2)
                        g3 = m.group(3)
                        if g2 and g1:
                            # schema.table.col
                            schema = g1; table_name = g2; col = g3
                        elif g2 and not g1:
                            # table.col (captured as g2=table, g3=col)
                            table_name = g2; col = g3; schema = None
                        else:
                            # only col? fallback
                            return field_text
                        # try to find alias for (schema,table) or by table only
                        alias = None
                        if schema:
                            alias = aliases.get((schema, table_name))
                        if not alias:
                            # search by table name only among selected tables
                            for s, tname in selected_tables:
                                if tname.lower() == table_name.lower():
                                    alias = aliases.get((s, tname))
                                    break
                        if alias:
                            return f"{alias}.[{col}]"
                        else:
                            # return fully qualified if schema known
                            if schema:
                                return f"[{schema}].[{table_name}].[{col}]"
                            else:
                                return f"[{table_name}].[{col}]"
                except Exception:
                    pass
                return field_text

            # Build select clause: if user selected columns, try to use aliases for them
            if not cols:
                select_clause = '*'
            else:
                cleaned = []
                for c in cols:
                    m = re.match(r"^([^\(]+)\s*(?:\(.*\))?$", c)
                    raw_field = m.group(1).strip() if m else c
                    # raw_field expected like 'table.col' or 'schema.table.col'
                    cleaned.append(_resolve_field_to_alias(raw_field))
                select_clause = ', '.join(cleaned)

            # Where (opcional) - prefer filtros parametrizados
            where_clause = ''
            if getattr(self, '_param_filters', None):
                try:
                    preview_items = []
                    for f in (self._param_filters or []):
                        try:
                            if isinstance(f, (list, tuple)):
                                expr = f[0] if len(f) >= 1 else str(f)
                                conn = f[3] if len(f) >= 4 else 'AND'
                            elif isinstance(f, dict):
                                expr = f.get('expr')
                                conn = f.get('connector', 'AND')
                            else:
                                expr = str(f); conn = 'AND'
                            # replace qualified field references with aliases
                            try:
                                # for each selected table, replace occurrences
                                new_expr = expr
                                for (schema, table_name), alias in aliases.items():
                                    if not alias:
                                        continue
                                    # pattern for [schema].[table].[col]
                                    pat1 = re.compile(rf"\[?{re.escape(schema)}\]?\s*\.\s*\[?{re.escape(table_name)}\]?\s*\.\s*\[?([A-Za-z0-9_]+)\]?", re.IGNORECASE)
                                    new_expr = pat1.sub(lambda m: f"{alias}.[{m.group(1)}]", new_expr)
                                    # pattern for table.col (no schema)
                                    pat2 = re.compile(rf"\b{re.escape(table_name)}\s*\.\s*([A-Za-z0-9_]+)\b", re.IGNORECASE)
                                    new_expr = pat2.sub(lambda m: f"{alias}.[{m.group(1)}]", new_expr)
                                expr = new_expr
                            except Exception:
                                pass
                            preview_items.append((expr, conn))
                        except Exception:
                            continue
                    if preview_items:
                        first_expr = preview_items[0][0]
                        w = first_expr
                        for expr, conn in preview_items[1:]:
                            w = f"{w} {conn} {expr}"
                        where_clause = w
                    else:
                        where_clause = ''
                except Exception:
                    try:
                        parts = []
                        for f in (self._param_filters or []):
                            if isinstance(f, (list, tuple)) and len(f) >= 1:
                                parts.append(f[0])
                            else:
                                parts.append(str(f))
                        where_clause = ' AND '.join(parts).strip()
                    except Exception:
                        where_clause = ''
            else:
                where_clause = self.where_input.toPlainText().strip()

            sql = f"SELECT {select_clause} FROM {from_clause}"
            if where_clause:
                sql += f" WHERE {where_clause}"

            # Preview
            self.sql_preview.setPlainText(sql)
            self.current_sql = sql

            # Log
            try:
                if getattr(self, 'session_logger', None):
                    self.session_logger.log('generate_sql', 'Gerou preview de SQL (manual)', {'preview': sql[:200]})
            except Exception:
                pass

        except Exception as e:
            QMessageBox.critical(self, "Erro ao gerar SQL (manual)", f"{e}")
        
    def on_modulo_changed(self, index: int):
        """Handler para quando o usuário muda o módulo na UI.

        Espera-se que exista um QComboBox `self.combo_modulo` conectado a este
        handler. O método armazena o value associado via `itemData(index)` em
        `self.current_modulo`.
        """
        try:
            if hasattr(self, 'combo_modulo') and self.combo_modulo is not None:
                self.current_modulo = self.combo_modulo.itemData(index)
        except Exception:
            pass

    def _flash_auto_update_badge(self):
        """Exibe o badge `auto_update_badge` com uma animação de fade in/out."""
        if not getattr(self, 'auto_update_badge', None):
            try:
                self.statusBar().showMessage('SQL atualizada automaticamente', 1500)
            except Exception:
                pass
            return
        try:
            badge = self.auto_update_badge
            badge.setVisible(True)
            effect = QGraphicsOpacityEffect(badge)
            badge.setGraphicsEffect(effect)
            anim_in = QPropertyAnimation(effect, b"opacity")
            anim_in.setDuration(250)
            anim_in.setStartValue(0.0)
            anim_in.setEndValue(1.0)
            # Keep reference to avoid GC
            self._badge_anim = anim_in
            anim_in.start()

            def _do_fade_out():
                try:
                    anim_out = QPropertyAnimation(effect, b"opacity")
                    anim_out.setDuration(400)
                    anim_out.setStartValue(1.0)
                    anim_out.setEndValue(0.0)
                    self._badge_anim = anim_out
                    anim_out.start()
                    QTimer.singleShot(410, lambda: badge.setVisible(False))
                except Exception:
                    try:
                        badge.setVisible(False)
                    except Exception:
                        pass

            # keep the badge visible for ~900ms before fading out
            QTimer.singleShot(900, _do_fade_out)
        except Exception:
            try:
                self.statusBar().showMessage('SQL atualizada automaticamente', 1500)
            except Exception:
                pass
            else:
                # fallback: tenta ler item text se itemData não estiver disponível
                if hasattr(self, 'combo_modulo') and self.combo_modulo is not None:
                    self.current_modulo = self.combo_modulo.itemText(index)
        except Exception:
            # não interrompe a UI
            self.current_modulo = None

    def _on_modulo_selected(self, index: int):
        """Internal handler: atualiza atributo e popula agrupamentos para o módulo selecionado."""
        try:
            # atualiza atributo público
            self.on_modulo_changed(index)
            module = getattr(self, 'current_modulo', None)
            if not module:
                return
            # carrega agrupamentos via QueryBuilder
            try:
                if getattr(self, '_debug_filter_populate', False):
                    try:
                        print(f"[DEBUG] _on_modulo_selected: module={module} index={index}")
                    except Exception:
                        pass
                agrup_meta = self.qb.carregar_agrupamentos(module)
                self.combo_agrupamento.clear()
                # populate with a neutral placeholder and keep signals blocked so
                # user must actively choose an agrupamento
                try:
                    self.combo_agrupamento.blockSignals(True)
                    self.combo_agrupamento.addItem("-- Selecione agrupamento --", None)
                    for a in agrup_meta.get('agrupamentos', []):
                        label = a.get('label') or a.get('id')
                        self.combo_agrupamento.addItem(label, a.get('id'))
                    # keep placeholder selected; do not auto-select the first real agrupamento
                    self.combo_agrupamento.setCurrentIndex(0)
                finally:
                    try:
                        self.combo_agrupamento.blockSignals(False)
                    except Exception:
                        pass
                # guarda agrupamento atual para uso posterior (população de campos ao selecionar)
                self._current_agrup_meta = agrup_meta
                # se já houver um agrupamento selecionado (por exemplo, reconstrução de estado), povoar campos
                try:
                    cur_idx = self.combo_agrupamento.currentIndex()
                    cur_id = self.combo_agrupamento.itemData(cur_idx)
                    if cur_id:
                        # populate fields translated according to mapping
                        self._populate_filter_fields(self._current_agrup_meta, cur_id)
                except Exception:
                    pass
            except Exception:
                # se falhar ao carregar agrupamentos, limpa combo
                try:
                    self.combo_agrupamento.clear()
                except Exception:
                    pass
        except Exception:
            pass

    def show_query_mode_help(self):
        """Exibe um diálogo explicando os dois modos de consulta."""
        try:
            msg = (
                "Modos de consulta:\n\n"
                "Metadados:\n"
                "  - Usa arquivos JSON de metadados para construir automaticamente a SQL\n"
                "  - Recomendado quando o módulo/agrupamentos estão disponíveis\n\n"
                "Manual:\n"
                "  - Permite selecionar tabelas e colunas livremente e montar a SQL manualmente\n"
                "  - Use quando você precisa de consultas ad-hoc que não estão cobertas pelos metadados\n\n"
                "Dica: alterne entre modos com os botões de rádio acima. Em 'Metadados' os controles manuais são desabilitados\n"
                "para evitar conflitos; em 'Manual' os combos de módulo/agrupamento ficam desabilitados."
            )
            QMessageBox.information(self, "Ajuda - Modos de Consulta", msg)
        except Exception:
            pass

    def on_agrupamento_changed(self, index: int):
        """Handler para quando o usuário muda o agrupamento na UI.

        Espera-se que exista um QComboBox `self.combo_agrupamento` conectado a
        este handler. Armazena o valor em `self.current_agrupamento_id`.
        """
        try:
            if hasattr(self, 'combo_agrupamento') and self.combo_agrupamento is not None:
                self.current_agrupamento_id = self.combo_agrupamento.itemData(index)
            else:
                if hasattr(self, 'combo_agrupamento') and self.combo_agrupamento is not None:
                    self.current_agrupamento_id = self.combo_agrupamento.itemText(index)
        except Exception:
            self.current_agrupamento_id = None

    def _on_agrupamento_selected(self, index: int):
        """Internal handler: atualiza o atributo público do agrupamento a partir do combo."""
        try:
            self.on_agrupamento_changed(index)
            # quando agrupamento muda, tentar popular campos de filtro com base no agrup_meta corrente
            try:
                if getattr(self, '_debug_filter_populate', False):
                    try:
                        print(f"[DEBUG] _on_agrupamento_selected: index={index} itemData={self.combo_agrupamento.itemData(index)}")
                    except Exception:
                        pass
                if not getattr(self, '_current_agrup_meta', None):
                    return
                agrup_id = self.combo_agrupamento.itemData(index)
                # only populate when a real agrupamento (non-placeholder) is selected
                if agrup_id:
                    self._populate_filter_fields(self._current_agrup_meta, agrup_id)
                else:
                    # clear filter fields if placeholder selected
                    try:
                        self.combo_filter_field.clear()
                        self.combo_filter_field.addItem("-- selecione um agrupamento --")
                        self.combo_filter_field.setEnabled(False)
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass

    def _on_filter_field_changed(self, index: int):
        """Atualiza quais widgets de entrada são exibidos conforme o tipo do campo selecionado."""
        try:
            data = self.combo_filter_field.itemData(index) or self.combo_filter_field.currentData()
            ftype = (data.get('type') if isinstance(data, dict) else None) if data else None
            if not ftype:
                ftype = 'text'

            # esconder tudo e mostrar apenas o que for necessário
            try:
                # texto
                self.filter_value_input.setVisible(False)
                # datas
                self.filter_date1.setVisible(False)
                self.filter_date2.setVisible(False)
                # números
                self.filter_num1.setVisible(False)
                self.filter_num2.setVisible(False)
            except Exception:
                pass

            if ftype == 'date':
                # ajusta formato do QDateEdit conforme preferências do MainWindow
                try:
                    main = self.window()
                    pyfmt = getattr(main, 'date_format', '%m-%d-%Y')
                    qtfmt = self._python_dateformat_to_qt(pyfmt)
                    self.filter_date1.setDisplayFormat(qtfmt)
                    self.filter_date2.setDisplayFormat(qtfmt)
                except Exception:
                    pass
                self.filter_date1.setVisible(True)
                # se operador for BETWEEN mostrar segundo
                if self.combo_filter_op.currentText() == 'BETWEEN':
                    self.filter_date2.setVisible(True)
                else:
                    self.filter_date2.setVisible(False)
            elif ftype == 'numeric':
                self.filter_num1.setVisible(True)
                if self.combo_filter_op.currentText() == 'BETWEEN':
                    self.filter_num2.setVisible(True)
                else:
                    self.filter_num2.setVisible(False)
            else:
                # texto default
                self.filter_value_input.setVisible(True)
                self.filter_value_input_to.setVisible(self.combo_filter_op.currentText() == 'BETWEEN')
        except Exception as e:
            print(f"Erro ao atualizar widgets de filtro: {e}")

    def _on_filter_op_changed(self, op: str):
        """Atualiza visibilidade do segundo valor quando operador é BETWEEN"""
        try:
            current_field_data = self.combo_filter_field.currentData()
            ftype = (current_field_data.get('type') if isinstance(current_field_data, dict) else None) if current_field_data else None
            if not ftype:
                ftype = 'text'

            if op == 'BETWEEN':
                if ftype == 'date':
                    try:
                        main = self.window()
                        pyfmt = getattr(main, 'date_format', '%m-%d-%Y')
                        qtfmt = self._python_dateformat_to_qt(pyfmt)
                        self.filter_date2.setDisplayFormat(qtfmt)
                    except Exception:
                        pass
                    self.filter_date2.setVisible(True)
                elif ftype == 'numeric':
                    self.filter_num2.setVisible(True)
                else:
                    self.filter_value_input_to.setVisible(True)
            else:
                # hide second inputs
                try:
                    self.filter_date2.setVisible(False)
                    self.filter_num2.setVisible(False)
                    self.filter_value_input_to.setVisible(False)
                except Exception:
                    pass
        except Exception as e:
            print(f"Erro ao atualizar operador de filtro: {e}")

    def _qualify_field(self, meta: dict) -> str:
        """Retorna a referência qualificada para uso em SQL a partir da meta do campo.

        Se meta contém uma expressão (por exemplo FORMAT(...)) e não contém table/column,
        retorna a expressão bruta. Se houver table/column/schema, tenta usar alias das
        tabelas selecionadas; se não houver alias, retorna [schema].[table].[column].
        """
        try:
            if not meta:
                return ''
            expr = meta.get('expr') or ''
            col = meta.get('column_name')
            table = meta.get('table_name')
            schema = meta.get('schema') or 'dbo'

            # if expr looks like a complex expression (contains '(' or whitespace), return as-is
            if expr and ("(" in expr or ")" in expr or ' ' in expr) and (not col or not table):
                return expr

            if col and table:
                # compute aliases for selected tables
                try:
                    aliases = self._compute_aliases_for_selected_tables()
                    alias = aliases.get((schema, table))
                except Exception:
                    alias = None

                if alias:
                    return f"{alias}.[{col}]"
                else:
                    return f"[{schema}].[{table}].[{col}]"

            # fallback: return expr or raw
            return expr or meta.get('expr') or ''
        except Exception:
            return meta.get('expr') if isinstance(meta, dict) else str(meta)

    def _python_dateformat_to_qt(self, pyfmt: str) -> str:
        """Converte um formato de data Python (ex: '%Y-%m-%d' ou '%d/%m/%Y') para um formato Qt (ex: 'yyyy-MM-dd' ou 'dd/MM/yyyy').

        Faz substituições simples — não cobre todos os casos complexos, mas atende aos formatos usados nas preferências.
        """
        try:
            if not pyfmt:
                return 'MM-dd-yyyy'
            s = pyfmt
            # replacements
            s = s.replace('%Y', 'yyyy')
            s = s.replace('%y', 'yy')
            s = s.replace('%m', 'MM')
            s = s.replace('%d', 'dd')
            s = s.replace('%b', 'MMM')
            s = s.replace('%B', 'MMMM')
            return s
        except Exception:
            return 'MM-dd-yyyy'

    def show_query_mode_help(self):
        """Exibe um diálogo explicando os dois modos de consulta."""
        try:
            msg = (
                "Modos de consulta:\n\n"
                "Metadados:\n"
                "  - Usa arquivos JSON de metadados para construir automaticamente a SQL\n"
                "  - Recomendado quando o módulo/agrupamentos estão disponíveis\n\n"
                "Manual:\n"
                "  - Permite selecionar tabelas e colunas livremente e montar a SQL manualmente\n"
                "  - Use quando você precisa de consultas ad-hoc que não estão cobertas pelos metadados\n\n"
                "Dica: alterne entre modos com os botões de rádio acima. Em 'Metadados' os controles manuais são desabilitados\n"
                "para evitar conflitos; em 'Manual' os combos de módulo/agrupamento ficam desabilitados."
            )
            QMessageBox.information(self, "Ajuda - Modos de Consulta", msg)
        except Exception:
            pass

    def _populate_filter_fields(self, agrup_meta: dict, agrupamento_id: str = None):
        """Preenche `self.combo_filter_field` com campos sugeridos a partir do agrupamento.

        Exibe dimensões (e some expressões derivadas) para que o usuário possa
        escolher onde aplicar filtros.
        """
        try:
            self.combo_filter_field.clear()
            # assume enabled; will disable if no fields found
            try:
                self.combo_filter_field.setEnabled(True)
            except Exception:
                pass
            # debug: mostrar informações iniciais sobre agrup_meta/agrupamento_id
            if getattr(self, '_debug_filter_populate', False):
                try:
                    print(f"[DEBUG] _populate_filter_fields called: agrupamento_id={agrupamento_id} tipo_agrup_meta={type(agrup_meta)}")
                    if isinstance(agrup_meta, dict):
                        keys = list(agrup_meta.keys())
                        print(f"[DEBUG] agrup_meta keys: {keys}")
                        if 'agrupamentos' in agrup_meta and isinstance(agrup_meta.get('agrupamentos'), list):
                            print(f"[DEBUG] agrup_meta.agrupamentos count: {len(agrup_meta.get('agrupamentos'))}")
                except Exception:
                    pass
            # tenta localizar o agrupamento pelo id
            agrup = None
            # If agrup_meta is not provided or malformed, try to reload from QueryBuilder
            if not agrup_meta or not isinstance(agrup_meta, dict):
                try:
                    agrup_meta = self.qb.carregar_agrupamentos(getattr(self, 'current_modulo', None))
                except Exception:
                    agrup_meta = agrup_meta or {}

            if agrupamento_id and 'agrupamentos' in agrup_meta:
                agrup = next((a for a in agrup_meta.get('agrupamentos', []) if a.get('id') == agrupamento_id), None)
            if agrup is None and 'agrupamentos' in agrup_meta:
                agrup = agrup_meta.get('agrupamentos', [])[0] if agrup_meta.get('agrupamentos') else None

            fields = []
            # build a quick mapping from column name -> friendly label using module metadata
            field_label_map = {}
            try:
                module = getattr(self, 'current_modulo', None)
                if module:
                    mod_meta = self.qb.carregar_modulo(module)
                    for tbl_key, tbl_def in (mod_meta.get('tabelas', {}) or {}).items():
                        for section in ('padrao', 'avancado'):
                            for c in (tbl_def.get('campos', {}).get(section, []) if isinstance(tbl_def.get('campos', {}), dict) else []):
                                try:
                                    nome = c.get('campo') if isinstance(c, dict) else str(c)
                                    # prefer explicit mapping override when available
                                    try:
                                        override = get_field_label(module, nome)
                                    except Exception:
                                        override = None
                                    if isinstance(c, dict) and c.get('label'):
                                        label = c.get('label')
                                    elif override:
                                        label = override
                                    else:
                                        label = nome
                                    field_label_map[nome.lower()] = label
                                except Exception:
                                    pass
            except Exception:
                field_label_map = {}
            if agrup:
                for dim in agrup.get('dimensoes', []):
                    # prioriza metadado explícito de tipo quando presente
                    detected_type = 'text'
                    if isinstance(dim, dict):
                        campo = dim.get('campo')
                        # check mapping override first
                        try:
                            override = get_field_label(getattr(self, 'current_modulo', None), campo)
                        except Exception:
                            override = None
                        if override:
                            label = override
                        else:
                            label = self._prettify_field_label(dim.get('label') or campo)
                        tipo = (dim.get('tipo') or '').lower()
                        if 'mes' in tipo or 'ano' in tipo or 'date' in tipo or 'data' in tipo:
                            detected_type = 'date'
                        elif any(k in tipo for k in ('int', 'decimal', 'numeric', 'float', 'money')):
                            detected_type = 'numeric'
                        else:
                            detected_type = 'text'
                        # save richer meta: try extract schema.table.column if provided
                        meta = {'expr': campo, 'type': detected_type}
                        # if campo contains '.', try to capture table/column
                        try:
                            parts = re.split(r"\.|\[|\]", campo)
                            # last two parts possibly table.column or schema.table.column
                            parts = [p for p in parts if p]
                            if len(parts) >= 2:
                                meta['column_name'] = parts[-1]
                                meta['table_name'] = parts[-2]
                                if len(parts) >= 3:
                                    meta['schema'] = parts[-3]
                        except Exception:
                            pass
                        fields.append((label, meta))
                    else:
                        # dim é string com nome do campo — tentar inferir
                        campo = dim
                        # try mapping override using the raw column name
                        try:
                            col_candidate = re.split(r"\.|\[|\]", dim)[-1]
                        except Exception:
                            col_candidate = dim
                        try:
                            override = get_field_label(getattr(self, 'current_modulo', None), col_candidate)
                        except Exception:
                            override = None
                        if override:
                            label = override
                        else:
                            label = self._prettify_field_label(dim)
                        # heurística: se o nome contém 'data' ou 'dt' assume date
                        lower = (campo or '').lower()
                        if 'data' in lower or lower.startswith('dt') or 'date' in lower:
                            detected_type = 'date'
                        else:
                            detected_type = 'text'

                        # tentar buscar no cache de colunas para detectar tipo real
                        try:
                            colname = re.split(r"\.|\[|\]", campo)[-1]
                            found = None
                            # busca em cache
                            for cols in self._columns_cache.values():
                                for c in cols:
                                    if c.column_name and c.column_name.lower() == colname.lower():
                                        found = c
                                        break
                                if found:
                                    break
                            if found:
                                dt = (found.data_type or '').lower()
                                if any(x in dt for x in ('date', 'time', 'datetime', 'timestamp')):
                                    detected_type = 'date'
                                elif any(x in dt for x in ('int', 'bigint', 'smallint', 'tinyint', 'decimal', 'numeric', 'float', 'real', 'money')):
                                    detected_type = 'numeric'
                                else:
                                    detected_type = 'text'
                        except Exception:
                            pass

                        # try to infer more accurate type by querying table metadata via QueryBuilder
                        meta = {'expr': campo, 'type': detected_type}
                        try:
                            # attempt to parse campo as possibly schema.table.column or table.column
                            parts = re.split(r"\.|\[|\]", campo)
                            parts = [p for p in parts if p]
                            colname = parts[-1] if parts else campo
                            tablename = parts[-2] if len(parts) >= 2 else None
                            schema = parts[-3] if len(parts) >= 3 else None
                            if tablename:
                                # query metadata via QueryBuilder to detect data type
                                try:
                                    cols = self.qb.get_table_columns(schema or 'dbo', tablename)
                                    for c in cols:
                                        if c.column_name and c.column_name.lower() == colname.lower():
                                            dt = (c.data_type or '').lower()
                                            if any(x in dt for x in ('date', 'time', 'datetime', 'timestamp')):
                                                meta['type'] = 'date'
                                            elif any(x in dt for x in ('int', 'bigint', 'smallint', 'tinyint', 'decimal', 'numeric', 'float', 'real', 'money')):
                                                meta['type'] = 'numeric'
                                            else:
                                                meta['type'] = 'text'
                                            meta['column_name'] = c.column_name
                                            meta['table_name'] = tablename
                                            meta['schema'] = schema or 'dbo'
                                            break
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        # attempt to replace raw label with friendly mapping from module meta
                        try:
                            colname = re.split(r"\.|\[|\]", campo)[-1]
                            if colname and colname.lower() in field_label_map:
                                label = field_label_map.get(colname.lower(), label)
                        except Exception:
                            pass
                        fields.append((label, meta))

            # adiciona campos ao combo (display -> data)
            for lbl, meta in fields:
                try:
                    self.combo_filter_field.addItem(lbl, meta)
                except Exception:
                    try:
                        # fallback: adicione apenas label
                        self.combo_filter_field.addItem(str(lbl))
                    except Exception:
                        pass
            if getattr(self, '_debug_filter_populate', False):
                try:
                    print(f"[DEBUG] fields extracted from agrupamento: {len(fields)}; combo_count(before fallback)={self.combo_filter_field.count()}")
                except Exception:
                    pass
            # se não houver campos detectados, tentar popular a partir dos metadados do módulo
            if not fields:
                try:
                    module = getattr(self, 'current_modulo', None)
                    if module:
                        try:
                            if getattr(self, '_debug_filter_populate', False):
                                try:
                                    print(f"[DEBUG] fallback: loading module meta for '{module}'")
                                except Exception:
                                    pass
                            mod_meta = self.qb.carregar_modulo(module)
                            # percorre tabelas e campos
                            for tbl_key, tbl_def in (mod_meta.get('tabelas', {}) or {}).items():
                                # campos padrão e avançado
                                for section in ('padrao', 'avancado'):
                                    for c in (tbl_def.get('campos', {}).get(section, []) if isinstance(tbl_def.get('campos', {}), dict) else []):
                                        try:
                                            nome = c.get('campo') if isinstance(c, dict) else str(c)
                                            label = c.get('label') if isinstance(c, dict) and c.get('label') else self._prettify_field_label(nome)
                                            tipo = (c.get('tipo') or '').lower() if isinstance(c, dict) else 'text'
                                            ftype = 'text'
                                            if 'date' in tipo or 'data' in tipo or 'mes' in tipo:
                                                ftype = 'date'
                                            elif any(k in tipo for k in ('int', 'decimal', 'numeric', 'float', 'money')):
                                                ftype = 'numeric'
                                            meta = {'expr': f"{tbl_key}.{nome}", 'type': ftype, 'table_name': tbl_key}
                                            self.combo_filter_field.addItem(label, meta)
                                        except Exception:
                                            continue
                            if getattr(self, '_debug_filter_populate', False):
                                try:
                                    print(f"[DEBUG] fallback added fields from module meta, combo_count={self.combo_filter_field.count()}")
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass

            # se ainda não houve campos detectados, mostrar um placeholder informativo
            if not fields and self.combo_filter_field.count() == 0:
                # fallback: tentar popular a partir das colunas atualmente selecionadas
                try:
                    fallback = []
                    # prioriza selected_columns_list (campos que o usuário já escolheu)
                    if hasattr(self, 'selected_columns_list'):
                        for i in range(self.selected_columns_list.count()):
                            txt = self.selected_columns_list.item(i).text()
                            if txt:
                                fallback.append((txt, {'expr': txt, 'type': 'text'}))
                    # senão, usa columns_list
                    if not fallback and hasattr(self, 'columns_list'):
                        for i in range(self.columns_list.count()):
                            txt = self.columns_list.item(i).text()
                            if txt:
                                fallback.append((txt, {'expr': txt, 'type': 'text'}))
                    if fallback:
                        for lbl, meta in fallback:
                            self.combo_filter_field.addItem(lbl, meta)
                    else:
                        self.combo_filter_field.addItem("Nenhum campo disponível")
                        self.combo_filter_field.setEnabled(False)
                except Exception:
                    try:
                        self.combo_filter_field.addItem("Nenhum campo disponível")
                        self.combo_filter_field.setEnabled(False)
                    except Exception:
                        pass
        except Exception as e:
            print(f"Falha ao popular campos de filtro: {e}")

    def _on_add_filter_clicked(self):
        """Cria expressão de filtro a partir dos controles e insere em where_input."""
        try:
            data = self.combo_filter_field.currentData()
            if not data:
                QMessageBox.warning(self, "Aviso", "Selecione um campo para filtrar.")
                return
            # monta referência qualificada do campo
            # se estivermos em modo manual, NÃO substituir o nome da tabela por alias —
            # mantém a referência tal como foi selecionada pelo usuário
            try:
                mode = getattr(self, 'modo_consulta', None) or getattr(self, 'modo_consulta', None)
            except Exception:
                mode = None
            if mode == 'manual':
                # se meta contém coluna/table/schema use estes valores
                try:
                    col = data.get('column_name') if isinstance(data, dict) else None
                    table = data.get('table_name') if isinstance(data, dict) else None
                    schema = data.get('schema') if isinstance(data, dict) else None
                except Exception:
                    col = table = schema = None
                if col and table:
                    schema = schema or 'dbo'
                    field_expr = f"[{schema}].[{table}].[{col}]"
                else:
                    # fallback: use raw expr but strip trailing datatype hints like ' (datetime)'
                    raw = data.get('expr') if isinstance(data, dict) else str(data)
                    if raw is None:
                        raw = ''
                    expr_clean = re.sub(r"\s*\([^\)]+\)\s*$", "", raw).strip()
                    field_expr = expr_clean
            else:
                # default behavior: use qualifying with aliases when possible
                field_expr = self._qualify_field(data)
            ftype = data.get('type') or 'text'
            op = self.combo_filter_op.currentText()

            # lê valores do widget correto conforme o tipo
            v1 = None
            v2 = None
            if ftype == 'date':
                # se widgets de data visíveis, usar seus valores
                try:
                    if self.filter_date1.isVisible():
                        v1 = self.filter_date1.date().toString('MM-dd-yyyy')
                    if self.filter_date2.isVisible():
                        v2 = self.filter_date2.date().toString('MM-dd-yyyy')
                except Exception:
                    v1 = None; v2 = None
            elif ftype == 'numeric':
                try:
                    if self.filter_num1.isVisible():
                        v1 = str(self.filter_num1.value())
                    if self.filter_num2.isVisible():
                        v2 = str(self.filter_num2.value())
                except Exception:
                    v1 = None; v2 = None
            else:
                # texto/libre
                v1 = self.filter_value_input.text().strip()
                v2 = self.filter_value_input_to.text().strip()

            if (not v1 or v1 == '') and op not in ('IN',):
                QMessageBox.warning(self, "Aviso", "Informe um valor para o filtro.")
                return

            def quote_text(s: str) -> str:
                # duplica aspas simples para evitar SQL injection simples (não é parametrizado)
                return "'" + s.replace("'", "''") + "'"

            expr = ''
            if op == 'BETWEEN':
                if not v2 or v2 == '':
                    QMessageBox.warning(self, "Aviso", "Informe o segundo valor para BETWEEN.")
                    return
                if ftype == 'numeric':
                    expr = f"{field_expr} BETWEEN {v1} AND {v2}"
                elif ftype == 'date':
                    a = quote_text(self.normalize_date(v1))
                    b = quote_text(self.normalize_date(v2))
                    expr = f"{field_expr} BETWEEN {a} AND {b}"
                else:
                    expr = f"{field_expr} BETWEEN {quote_text(v1)} AND {quote_text(v2)}"
            elif op == 'IN':
                # split por vírgula e quote cada item conforme tipo
                raw = v1 or ''
                items = [s.strip() for s in raw.split(',') if s.strip()]
                if not items:
                    QMessageBox.warning(self, "Aviso", "Informe pelo menos um valor para IN.")
                    return
                if ftype == 'numeric':
                    quoted = ', '.join([str(float(it)) if re.match(r"^[\d\-\.]+$", it) else it for it in items])
                elif ftype == 'date':
                    quoted = ', '.join([quote_text(self.normalize_date(it)) for it in items])
                else:
                    quoted = ', '.join([quote_text(it) for it in items])
                expr = f"{field_expr} IN ({quoted})"
            elif op == 'LIKE':
                if ftype == 'numeric':
                    expr = f"{field_expr} LIKE {v1}"
                else:
                    expr = f"{field_expr} LIKE {quote_text(v1)}"
            else:
                # comparadores simples
                if ftype == 'numeric':
                    expr = f"{field_expr} {op} {v1}"
                elif ftype == 'date':
                    expr = f"{field_expr} {op} {quote_text(self.normalize_date(v1))}"
                else:
                    expr = f"{field_expr} {op} {quote_text(v1)}"

            # prepare parametrized filter (expr, params)
            params = []
            # determine params based on operator and type
            if op == 'BETWEEN':
                if ftype == 'numeric':
                    try:
                        a = float(v1)
                        b = float(v2)
                    except Exception:
                        a = v1; b = v2
                    param_expr = f"{field_expr} BETWEEN ? AND ?"
                    params = [a, b]
                elif ftype == 'date':
                    a = self._date_to_iso(v1)
                    b = self._date_to_iso(v2)
                    param_expr = f"{field_expr} BETWEEN ? AND ?"
                    params = [a, b]
                else:
                    param_expr = f"{field_expr} BETWEEN ? AND ?"
                    params = [v1, v2]
            elif op == 'IN':
                raw = v1 or ''
                items = [s.strip() for s in raw.split(',') if s.strip()]
                if not items:
                    QMessageBox.warning(self, "Aviso", "Informe pelo menos um valor para IN.")
                    return
                placeholders = ', '.join(['?'] * len(items))
                param_expr = f"{field_expr} IN ({placeholders})"
                if ftype == 'numeric':
                    conv = []
                    for it in items:
                        try:
                            conv.append(float(it))
                        except Exception:
                            conv.append(it)
                    params = conv
                elif ftype == 'date':
                    params = [self._date_to_iso(it) for it in items]
                else:
                    params = [it for it in items]
            elif op == 'LIKE':
                param_expr = f"{field_expr} LIKE ?"
                if ftype == 'numeric':
                    params = [v1]
                else:
                    params = [v1]
            else:
                # comparadores simples
                param_expr = f"{field_expr} {op} ?"
                if ftype == 'numeric':
                    try:
                        params = [int(v1) if str(v1).isdigit() else float(v1)]
                    except Exception:
                        params = [v1]
                elif ftype == 'date':
                    params = [self._date_to_iso(v1)]
                else:
                    params = [v1]

            # adiciona à lista parametrizada
            try:
                # store meta together to allow editing/changing field later
                # connector selected in the panel (AND/OR)
                try:
                    conn = self.filter_connector_combo.currentText() if getattr(self, 'filter_connector_combo', None) else 'AND'
                except Exception:
                    conn = 'AND'
                self._param_filters.append((param_expr, params, data, conn))
            except Exception:
                pass

            # atualiza a lista visível de filtros parametrizados
            try:
                self._refresh_filters_list()
            except Exception:
                pass

            # preview textual no WHERE já é atualizado por _refresh_filters_list()

            # log
            try:
                if getattr(self, 'session_logger', None):
                    self.session_logger.log('add_filter', 'Filtro adicionado (parametrizado)', {'expr': param_expr, 'params_count': len(params)})
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao adicionar filtro:\n{e}")

    # --- Gerenciamento de filtros parametrizados (lista / remover / limpar) ---
    def _format_param_filter_preview(self, expr: str, params: list) -> str:
        """Gera uma representação legível do filtro parametrizado para exibir na lista."""
        try:
            def fmt(p):
                if p is None:
                    return 'NULL'
                if isinstance(p, (int, float)):
                    return str(p)
                # datas em formato ISO - mostrar com aspas
                return f"'{p}'"
            if not params:
                return expr
            # tenta substituir apenas placeholders para tornar preview legível
            if expr.count('?') == len(params):
                parts = expr.split('?')
                out = ''.join(parts[i] + (fmt(params[i]) if i < len(params) else '') for i in range(len(parts)))
                # append trailing part
                if len(parts) > len(params):
                    out = out
                return out
            # fallback: show expr + params
            return f"{expr} [{', '.join(fmt(p) for p in params)}]"
        except Exception:
            try:
                return f"{expr} [{', '.join(map(str, params))}]"
            except Exception:
                return expr

    def _refresh_filters_list(self):
        """Atualiza `self.filters_list` a partir de `self._param_filters` e reconstroi o preview em `where_input`."""
        try:
            # salva texto atual do WHERE para permitir desfazer
            try:
                prev_where = self.where_input.toPlainText()
            except Exception:
                prev_where = ''

            self.filters_list.clear()
            # (Removido: não mantemos mais a lista separada de "filtros incluídos")
            previews = []
            for item in (self._param_filters or []):
                # suportar formatos antigos e novos
                expr = None; params = None; meta = None; connector = 'AND'
                try:
                    if isinstance(item, (list, tuple)):
                        if len(item) >= 2:
                            expr = item[0]; params = item[1]
                        if len(item) >= 3:
                            meta = item[2]
                        if len(item) >= 4:
                            try:
                                connector = item[3]
                            except Exception:
                                connector = 'AND'
                    elif isinstance(item, dict):
                        expr = item.get('expr'); params = item.get('params'); meta = item.get('meta')
                        connector = item.get('connector', 'AND')
                except Exception:
                    continue
                pv = self._format_param_filter_preview(expr, params)
                # criar item vazio (texto será mostrado pelo widget embutido)
                it = QListWidgetItem()
                # armazenar a tupla (expr, params, meta, connector) no UserRole
                it.setData(Qt.UserRole, (expr, params, meta, connector))
                self.filters_list.addItem(it)
                # tentar criar widget customizado (combo de conector + texto)
                try:
                    container = QWidget()
                    h = QHBoxLayout(container)
                    h.setContentsMargins(6, 2, 6, 2)
                    # embed a small combo to allow editing the connector per-item
                    conn_combo = QComboBox()
                    conn_combo.addItems(["AND", "OR"])
                    try:
                        conn_combo.setCurrentText(str(connector).strip().upper())
                    except Exception:
                        try:
                            conn_combo.setCurrentText('AND')
                        except Exception:
                            pass
                    conn_combo.setFixedWidth(64)
                    # style the combo a bit for visibility
                    conn_combo.setStyleSheet('padding:2px; border-radius:6px;')
                    expr_lbl = QLabel(pv)
                    expr_lbl.setWordWrap(True)
                    expr_lbl.setTextInteractionFlags(expr_lbl.textInteractionFlags() | Qt.TextSelectableByMouse)
                    try:
                        # reduzir fonte para melhorar encaixe em telas menores
                        f = expr_lbl.font()
                        f.setPointSize(10)
                        expr_lbl.setFont(f)
                    except Exception:
                        pass
                    try:
                        expr_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    except Exception:
                        pass
                    try:
                        # aplicar elisão horizontal para textos muito longos
                        max_w = 0
                        try:
                            max_w = self.filters_list.viewport().width() - 100
                        except Exception:
                            max_w = 300
                        if max_w > 30:
                            fm = QFontMetrics(expr_lbl.font())
                            el = fm.elidedText(pv, Qt.ElideRight, max_w)
                            expr_lbl.setText(el)
                    except Exception:
                        pass
                    # NOTE: removemos o widget de seleção do conector da lista "Gerenciar filtros"
                    # para simplificar a UI conforme solicitado. O conector continua sendo
                    # armazenado em Qt.UserRole para uso na geração da SQL, mas não é
                    # exibido nem editável diretamente nesta lista.
                    h.addWidget(expr_lbl)
                    h.addStretch()
                    self.filters_list.setItemWidget(it, container)
                    # assegurar que o QListWidgetItem tenha o tamanho do widget
                    try:
                        it.setSizeHint(container.sizeHint())
                    except Exception:
                        pass
                    # limpar texto do item para evitar sobreposição entre o
                    # texto interno do QListWidgetItem e o widget customizado
                    try:
                        it.setText('')
                    except Exception:
                        pass
                    # (Removido) não conectamos mais signals para edição do conector aqui.
                except Exception:
                    # fallback: item de texto simples
                    pass
                previews.append((pv, connector))
                # (Removido: anteriormente adicionávamos também na lista central de
                # filtros incluídos. Agora todo filtro vai para o gerenciador de
                # filtros (`self.filters_list`) e não mantemos essa visualização
                # duplicada.)

            # sincroniza WHERE sempre com os filtros parametrizados
            # monta where respeitando conectores por filtro (armazenados como 4a posição)
            new_where = ''
            try:
                if previews:
                    # previews is list of (pv, connector)
                    first = previews[0][0]
                    parts = [first]
                    for pv, conn in previews[1:]:
                        parts.append(f" {conn} {pv}")
                    new_where = ''.join(parts)
                else:
                    new_where = ''
            except Exception:
                # fallback para compatibilidade: juntar com AND
                try:
                    new_where = ' AND '.join(p[0] if isinstance(p, tuple) else str(p) for p in previews)
                except Exception:
                    new_where = ''
            # se houve alteração efetiva no WHERE, guarda no histórico para permitir múltiplos undo
            if new_where != prev_where:
                try:
                    # inicializa history se necessário
                    if not hasattr(self, '_where_history'):
                        self._where_history = []
                        self._where_history_limit = 50
                    # empilha valor anterior
                    self._where_history.append(prev_where)
                    # clear redo stack on new action
                    try:
                        self._where_redo = []
                    except Exception:
                        pass
                    # limita tamanho
                    if len(self._where_history) > getattr(self, '_where_history_limit', 50):
                        self._where_history.pop(0)
                except Exception:
                    pass
            # habilita/desabilita botão de desfazer conforme histórico
            try:
                has_hist = bool(getattr(self, '_where_history', []))
                self.btn_undo_where.setEnabled(has_hist)
            except Exception:
                pass
            try:
                self.where_input.setPlainText(new_where)
            except Exception:
                pass
            # If we're in manual mode, regenerate the manual SQL preview so
            # the newly added filters are reflected immediately without
            # requiring the user to click 'Gerar SQL'. This keeps behavior
            # intuitive when users add filters via context menu.
            try:
                if getattr(self, 'modo_consulta', 'metadados') == 'manual':
                    # regenerate manual SQL preview and current_sql
                    try:
                        self.generate_sql_manual()
                        # show a small badge with fade animation to indicate automatic regeneration
                        try:
                            try:
                                if getattr(self, '_flash_auto_update_badge', None):
                                    # call method if present
                                    self._flash_auto_update_badge()
                                else:
                                    # fallback behavior
                                    if getattr(self, 'auto_update_badge', None):
                                        self.auto_update_badge.setVisible(True)
                                        QTimer.singleShot(1500, lambda: self.auto_update_badge.setVisible(False))
                                    else:
                                        self.statusBar().showMessage('SQL atualizada automaticamente', 1500)
                            except Exception:
                                pass
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception as e:
            print(f"Erro ao atualizar lista de filtros: {e}")

    def _remove_selected_filter(self):
        """Remove os filtros selecionados na lista (mantém ordem dos demais)."""
        try:
            sel = self.filters_list.selectedIndexes()
            if not sel:
                QMessageBox.information(self, "Informação", "Selecione ao menos um filtro para remover.")
                return
            # coleta índices únicos e ordena descendente para remover sem reindexar problemas
            idxs = sorted({i.row() for i in sel}, reverse=True)
            for i in idxs:
                try:
                    self._param_filters.pop(i)
                except Exception:
                    pass
            # atualiza lista e preview
            self._refresh_filters_list()
            try:
                if getattr(self, 'session_logger', None):
                    self.session_logger.log('remove_filter', f'Removeu {len(idxs)} filtro(s)')
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao remover filtros:\n{e}")

    def _edit_selected_filter(self):
        """Edita um filtro selecionado com widgets adequados ao tipo (data/número/texto) e operador.

        Permite editar operador e valores. Ao salvar, atualiza `self._param_filters` e a visualização.
        """
        try:
            sel = self.filters_list.selectedItems()
            if not sel:
                QMessageBox.information(self, "Informação", "Selecione exatamente um filtro para editar.")
                return
            if len(sel) > 1:
                QMessageBox.information(self, "Informação", "Selecione apenas um filtro para editar.")
                return
            item = sel[0]
            data = item.data(Qt.UserRole)
            if not data or not isinstance(data, (list, tuple)):
                QMessageBox.warning(self, "Aviso", "Filtro inválido para edição.")
                return
            # support stored formats: (expr, params) or (expr, params, meta)
            expr = data[0] if len(data) > 0 else None
            params = data[1] if len(data) > 1 else []
            meta = data[2] if len(data) > 2 else None

            # tenta inferir field e operador a partir da expressão parametrizada
            field = expr
            op = None
            m = re.search(r"\bBETWEEN\b", expr, re.IGNORECASE)
            if m:
                op = 'BETWEEN'
                field = re.split(r"\bBETWEEN\b", expr, flags=re.IGNORECASE)[0].strip()
            elif re.search(r"\bIN\s*\(", expr, re.IGNORECASE):
                op = 'IN'
                field = re.split(r"\bIN\s*\(", expr, flags=re.IGNORECASE)[0].strip()
            elif re.search(r"\bIS\s+NULL\b", expr, re.IGNORECASE):
                op = 'IS NULL'
                field = re.split(r"\bIS\s+NULL\b", expr, flags=re.IGNORECASE)[0].strip()
            else:
                # comparadores simples e LIKE
                m2 = re.search(r"(?P<field>.+?)\s*(?P<op>>=|<=|!=|<>|=|>|<|LIKE)\s*(?P<rest>.+)$", expr, re.IGNORECASE)
                if m2:
                    op = m2.group('op').upper()
                    field = m2.group('field').strip()
            if not op:
                # fallback para '='
                op = '='

            # detecta tipo a partir dos parâmetros atuais ou metadata (preferível)
            detected_type = 'text'
            try:
                # prefer meta if available
                if meta and isinstance(meta, dict) and meta.get('type'):
                    detected_type = meta.get('type')
                elif params:
                    all_num = True
                    all_date = True
                    for p in params:
                        if isinstance(p, (int, float)):
                            all_date = False
                            continue
                        s = str(p)
                        # numeric?
                        if re.match(r'^-?\d+(?:\.\d+)?$', s):
                            all_date = False
                            continue
                        all_num = False
                        # date?
                        try:
                            vv = s
                            if vv.endswith('Z') or vv.endswith('z'):
                                vv = vv[:-1] + '+00:00'
                            _dt.datetime.fromisoformat(vv)
                        except Exception:
                            all_date = False
                    if all_num and not all_date:
                        detected_type = 'numeric'
                    elif all_date and not all_num:
                        detected_type = 'date'
                    else:
                        detected_type = 'text'
            except Exception:
                detected_type = 'text'

            # constrói diálogo de edição
            dlg = QDialog(self)
            dlg.setWindowTitle("Editar filtro")
            dlg.setMinimumWidth(520)
            layout = QVBoxLayout(dlg)

            # campo: permitir troca — popula com campos atualmente disponíveis no agrupamento
            field_combo = QComboBox()
            # try to populate from combo_filter_field entries (which hold meta)
            try:
                for i in range(self.combo_filter_field.count()):
                    lbl = self.combo_filter_field.itemText(i)
                    meta_item = self.combo_filter_field.itemData(i)
                    field_combo.addItem(lbl, meta_item)
                # try select the current field by matching the field expression
                try:
                    # match by meta if available
                    sel_idx = None
                    for i in range(field_combo.count()):
                        md = field_combo.itemData(i)
                        if md and isinstance(md, dict) and md.get('expr') and md.get('expr') == field:
                            sel_idx = i; break
                    if sel_idx is None:
                        # try matching by display label
                        for i in range(field_combo.count()):
                            if field_combo.itemText(i).strip() == field:
                                sel_idx = i; break
                    if sel_idx is not None:
                        field_combo.setCurrentIndex(sel_idx)
                except Exception:
                    pass
            except Exception:
                # fallback: show raw field text only
                field_combo.addItem(field, None)

            layout.addWidget(QLabel(f"Campo:"))
            layout.addWidget(field_combo)

            # tipo (permite ao usuário forçar interpretação do campo)
            type_combo = QComboBox()
            type_combo.addItems(["Texto", "Numérico", "Data"])
            # define seleção atual
            try:
                if detected_type == 'numeric':
                    type_combo.setCurrentText('Numérico')
                elif detected_type == 'date':
                    type_combo.setCurrentText('Data')
                else:
                    type_combo.setCurrentText('Texto')
            except Exception:
                pass
            layout.addWidget(QLabel('Tipo:'))
            layout.addWidget(type_combo)

            # operador
            op_combo = QComboBox()
            ops = ["=", "!=", ">", "<", ">=", "<=", "BETWEEN", "IN", "LIKE", "IS NULL"]
            op_combo.addItems(ops)
            try:
                op_combo.setCurrentText(op)
            except Exception:
                pass
            layout.addWidget(QLabel("Operador:"))
            layout.addWidget(op_combo)

            # area de widgets para valores
            val_area = QVBoxLayout()

            # texto simples / IN - QLineEdit
            txt_single = QLineEdit()
            txt_single.setPlaceholderText('Valor')

            # IN editor: token-based list (visual)
            token_widget = QListWidget()
            token_widget.setSelectionMode(QListWidget.ExtendedSelection)
            token_input_layout = QHBoxLayout()
            token_input = QLineEdit()
            token_input.setPlaceholderText('Adicionar valor e pressionar Enter')
            token_add_btn = QPushButton('+')
            token_input_layout.addWidget(token_input)
            token_input_layout.addWidget(token_add_btn)
            # helper to add token
            def _add_token():
                txt = token_input.text().strip()
                if not txt:
                    return
                # avoid duplicates
                for i in range(token_widget.count()):
                    if token_widget.item(i).text() == txt:
                        token_input.clear(); return
                it = QListWidgetItem(txt)
                token_widget.addItem(it)
                token_input.clear()
            token_add_btn.clicked.connect(_add_token)
            token_input.returnPressed.connect(_add_token)

            # suporte a remoção/edição via tecla Delete e menu de contexto
            def _remove_selected_tokens():
                sel = token_widget.selectedItems()
                if not sel:
                    return
                for it in sel:
                    row = token_widget.row(it)
                    token_widget.takeItem(row)

            def _edit_token(item: QListWidgetItem):
                try:
                    old = item.text()
                    new, ok = QInputDialog.getText(dlg, 'Editar token', 'Valor:', QLineEdit.Normal, old)
                    if ok and new and new.strip() and new.strip() != old:
                        # evitar duplicatas
                        new = new.strip()
                        for i in range(token_widget.count()):
                            if token_widget.item(i).text() == new:
                                QMessageBox.warning(dlg, 'Duplicado', 'Valor já existe na lista de tokens.'); return
                        item.setText(new)
                except Exception:
                    pass

            # context menu
            token_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            def _on_token_context(pos):
                try:
                    menu = QMenu()
                    act_remove = QAction('Remover', dlg)
                    act_edit = QAction('Editar', dlg)
                    act_remove.triggered.connect(_remove_selected_tokens)
                    menu.addAction(act_remove)
                    # allow edit only if single selection
                    if len(token_widget.selectedItems()) == 1:
                        act_edit.triggered.connect(lambda: _edit_token(token_widget.selectedItems()[0]))
                        menu.addAction(act_edit)
                    menu.exec_(token_widget.mapToGlobal(pos))
                except Exception:
                    pass
            token_widget.customContextMenuRequested.connect(_on_token_context)

            # double click => edit
            token_widget.itemDoubleClicked.connect(lambda it: _edit_token(it))

            # event filter to catch Delete key
            class _TokenEventFilter(QObject):
                def __init__(self, parent=None):
                    super().__init__(parent)
                def eventFilter(self, obj, event):
                    try:
                        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Delete:
                            _remove_selected_tokens()
                            return True
                    except Exception:
                        pass
                    return False
            try:
                ef = _TokenEventFilter(token_widget)
                token_widget._token_event_filter = ef
                token_widget.installEventFilter(ef)
                # garantir que o widget receba foco para capturar teclas
                token_widget.setFocusPolicy(Qt.StrongFocus)
            except Exception:
                pass

            # numericos
            num_single = QDoubleSpinBox()
            num_single.setRange(-1e12, 1e12)
            num_single.setDecimals(6)

            num_a = QDoubleSpinBox()
            num_a.setRange(-1e12, 1e12)
            num_a.setDecimals(6)
            num_b = QDoubleSpinBox()
            num_b.setRange(-1e12, 1e12)
            num_b.setDecimals(6)

            # datas
            date_single = QDateEdit()
            date_single.setCalendarPopup(True)
            date_single.setDisplayFormat(self._python_dateformat_to_qt(getattr(self.window(), 'date_format', '%m-%d-%Y')))
            try:
                date_single.setDate(QDate.currentDate())
            except Exception:
                pass

            date_a = QDateEdit()
            date_a.setCalendarPopup(True)
            date_a.setDisplayFormat(self._python_dateformat_to_qt(getattr(self.window(), 'date_format', '%m-%d-%Y')))
            try:
                date_a.setDate(QDate.currentDate())
            except Exception:
                pass
            date_b = QDateEdit()
            date_b.setCalendarPopup(True)
            date_b.setDisplayFormat(self._python_dateformat_to_qt(getattr(self.window(), 'date_format', '%m-%d-%Y')))
            try:
                date_b.setDate(QDate.currentDate())
            except Exception:
                pass

            # Inicializa valores a partir de params
            try:
                if detected_type == 'numeric':
                    if params:
                        if len(params) >= 1:
                            num_single.setValue(float(params[0]))
                        if len(params) >= 2:
                            num_a.setValue(float(params[0])); num_b.setValue(float(params[1]))
                elif detected_type == 'date':
                    def try_set_date(widget, s):
                        try:
                            vv = s
                            if vv.endswith('Z') or vv.endswith('z'):
                                vv = vv[:-1] + '+00:00'
                            dt = _dt.datetime.fromisoformat(vv)
                            widget.setDate(QDate(dt.year, dt.month, dt.day))
                        except Exception:
                            try:
                                # try parsing as YYYY-MM-DD
                                dt = _dt.datetime.strptime(str(s)[:10], '%Y-%m-%d')
                                widget.setDate(QDate(dt.year, dt.month, dt.day))
                            except Exception:
                                pass
                    if params:
                        if len(params) >= 1:
                            try_set_date(date_single, params[0])
                        if len(params) >= 2:
                            try_set_date(date_a, params[0]); try_set_date(date_b, params[1])
                else:
                    if params:
                        if op == 'IN':
                            try:
                                token_widget.clear()
                                for p in params:
                                    token_widget.addItem(QListWidgetItem(str(p)))
                            except Exception:
                                pass
                        elif op == 'BETWEEN' and len(params) >= 2:
                            txt_single.setText(str(params[0]));
                            try:
                                token_widget.clear()
                                token_widget.addItem(QListWidgetItem(str(params[1])))
                            except Exception:
                                pass
                        else:
                            txt_single.setText(str(params[0]))
            except Exception:
                pass

            # add widgets to layout but control visibility
            val_area.addWidget(txt_single)
            # IN token editor area
            val_area.addWidget(token_widget)
            val_area.addLayout(token_input_layout)
            val_area.addWidget(num_single)
            h_ab = QHBoxLayout()
            h_ab.addWidget(num_a); h_ab.addWidget(num_b)
            val_area.addLayout(h_ab)
            val_area.addWidget(date_single)
            h_dates = QHBoxLayout(); h_dates.addWidget(date_a); h_dates.addWidget(date_b)
            val_area.addLayout(h_dates)

            layout.addLayout(val_area)

            # helper para ajustar visibilidade
            def update_value_widgets(op_text=None, dtype=None):
                if op_text is None:
                    o = op_combo.currentText()
                else:
                    o = op_text
                dtp = dtype or detected_type
                # hide all initially
                for w in (txt_single, token_widget, token_input, token_add_btn, num_single, num_a, num_b, date_single, date_a, date_b):
                    try:
                        w.setVisible(False)
                    except Exception:
                        pass
                if o == 'IS NULL':
                    return
                if o == 'IN':
                    # show token editor for IN values
                    token_widget.setVisible(True); token_input.setVisible(True); token_add_btn.setVisible(True)
                    return
                if o == 'BETWEEN':
                    if dtp == 'numeric':
                        num_a.setVisible(True); num_b.setVisible(True)
                    elif dtp == 'date':
                        date_a.setVisible(True); date_b.setVisible(True)
                    else:
                        # text between uses a second value: use txt_single and token_widget for second
                        txt_single.setVisible(True); token_widget.setVisible(True); token_input.setVisible(True); token_add_btn.setVisible(True)
                    return
                # simple comparators and LIKE
                if dtp == 'numeric':
                    num_single.setVisible(True)
                elif dtp == 'date':
                    date_single.setVisible(True)
                else:
                    txt_single.setVisible(True)

            # connect operator and type changes
            op_combo.currentTextChanged.connect(lambda _: update_value_widgets())
            def on_type_change(text):
                tmap = 'text'
                if text == 'Numérico':
                    tmap = 'numeric'
                elif text == 'Data':
                    tmap = 'date'
                update_value_widgets(None, tmap)
            type_combo.currentTextChanged.connect(on_type_change)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            layout.addWidget(buttons)

            def accept_changes():
                new_op = op_combo.currentText()
                new_params = []
                # collect values according to widgets visible
                try:
                    if new_op == 'IS NULL':
                        param_expr = f"{field} IS NULL"
                        new_params = []
                    elif new_op == 'IN':
                        # collect tokens from the token widget
                        parts = [token_widget.item(i).text() for i in range(token_widget.count())]
                        # fallback: allow typing directly in the input
                        if not parts:
                            raw = token_input.text().strip()
                            parts = [p.strip() for p in raw.split(',') if p.strip()]
                        if not parts:
                            QMessageBox.warning(dlg, 'Valor ausente', 'Informe pelo menos um valor para IN.')
                            return
                        placeholders = ', '.join(['?'] * len(parts))
                        param_expr = f"{field} IN ({placeholders})"
                        if detected_type == 'numeric':
                            conv = []
                            for p in parts:
                                try:
                                    conv.append(int(p) if re.match(r'^-?\d+$', p) else float(p))
                                except Exception:
                                    conv.append(p)
                            new_params = conv
                        elif detected_type == 'date':
                            new_params = [self._date_to_iso(p) for p in parts]
                        else:
                            new_params = parts
                    elif new_op == 'BETWEEN':
                        if detected_type == 'numeric':
                            a = num_a.value(); b = num_b.value()
                            param_expr = f"{field} BETWEEN ? AND ?"
                            new_params = [a, b]
                        elif detected_type == 'date':
                            a_q = date_a.date(); b_q = date_b.date()
                            a = f"{a_q.year()}-{a_q.month():02d}-{a_q.day():02d}"
                            b = f"{b_q.year()}-{b_q.month():02d}-{b_q.day():02d}"
                            param_expr = f"{field} BETWEEN ? AND ?"
                            new_params = [a, b]
                        else:
                            a = txt_single.text().strip()
                            # second value may be in token widget or typed directly
                            if token_widget.count() > 0:
                                b = token_widget.item(0).text().strip()
                            else:
                                b = token_input.text().strip()
                            if not a or not b:
                                QMessageBox.warning(dlg, 'Valor ausente', 'Para BETWEEN informe ambos os valores.')
                                return
                            param_expr = f"{field} BETWEEN ? AND ?"
                            new_params = [a, b]
                    else:
                        # simple comparator or LIKE
                        if detected_type == 'numeric':
                            v = num_single.value()
                            param_expr = f"{field} {new_op} ?"
                            new_params = [v]
                        elif detected_type == 'date':
                            dq = date_single.date()
                            v = f"{dq.year()}-{dq.month():02d}-{dq.day():02d}"
                            param_expr = f"{field} {new_op} ?"
                            new_params = [v]
                        else:
                            v = txt_single.text().strip()
                            if not v and new_op != 'IS NULL':
                                QMessageBox.warning(dlg, 'Valor ausente', 'Informe um valor para o filtro.')
                                return
                            param_expr = f"{field} {new_op} ?"
                            new_params = [v]
                except Exception as ee:
                    QMessageBox.critical(dlg, 'Erro', f'Falha ao montar parâmetros: {ee}')
                    return

                # localizar índice do item e atualizar
                idx = None
                for i in range(self.filters_list.count()):
                    if self.filters_list.item(i) is item:
                        idx = i
                        break
                if idx is None:
                    QMessageBox.warning(dlg, 'Aviso', 'Não foi possível localizar o filtro selecionado.')
                    return
                try:
                    # preserve existing meta/connector if present
                    old = self._param_filters[idx]
                    try:
                        old_meta = old[2] if len(old) >= 3 else None
                    except Exception:
                        old_meta = None
                    try:
                        old_conn = old[3] if len(old) >= 4 else (old.get('connector') if isinstance(old, dict) else 'AND')
                    except Exception:
                        old_conn = 'AND'
                    self._param_filters[idx] = (param_expr, new_params, old_meta, old_conn)
                except Exception as e:
                    QMessageBox.critical(dlg, 'Erro', f'Falha ao salvar filtro: {e}')
                    return
                dlg.accept()

            buttons.accepted.connect(accept_changes)
            buttons.rejected.connect(dlg.reject)

            # inicializa visibilidade dos widgets com base no operador detectado
            update_value_widgets(op, detected_type)

            if dlg.exec_() == QDialog.Accepted:
                # atualiza UI/lista e log
                self._refresh_filters_list()
                try:
                    if getattr(self, 'session_logger', None):
                        self.session_logger.log('edit_filter', 'Filtro editado (avançado)', {'field': field, 'op': op})
                except Exception:
                    pass
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao editar filtro:\n{e}")

    def _undo_last_where(self):
        """Restaura o texto do WHERE antes da última sincronização feita por `_refresh_filters_list`."""
        hist = getattr(self, '_where_history', [])
        if not hist:
            QMessageBox.information(self, "Informação", "Nenhum estado anterior do WHERE disponível para desfazer.")
            return
        prev = None
        try:
            prev = hist.pop()
        except Exception:
            prev = None
        if prev is None:
            QMessageBox.information(self, "Informação", "Nenhum estado anterior do WHERE disponível para desfazer.")
            return
        # empilha estado atual no redo
        try:
            cur = self.where_input.toPlainText()
            if not hasattr(self, '_where_redo'):
                self._where_redo = []
            self._where_redo.append(cur)
            if len(self._where_redo) > getattr(self, '_where_history_limit', 50):
                self._where_redo.pop(0)
        except Exception:
            pass
        # restaura texto
        try:
            self.where_input.setPlainText(prev)
        except Exception:
            pass

    def _redo_last_where(self):
        """Refaz o último estado do WHERE que foi desfeito."""
        redo = getattr(self, '_where_redo', [])
        if not redo:
            QMessageBox.information(self, "Informação", "Nenhum estado disponível para refazer.")
            return
        next_val = None
        try:
            next_val = redo.pop()
        except Exception:
            next_val = None
        if next_val is None:
            QMessageBox.information(self, "Informação", "Nenhum estado disponível para refazer.")
            return
        # empilha estado atual no histórico de desfazer
        try:
            cur = self.where_input.toPlainText()
            if not hasattr(self, '_where_history'):
                self._where_history = []
            self._where_history.append(cur)
            if len(self._where_history) > getattr(self, '_where_history_limit', 50):
                self._where_history.pop(0)
        except Exception:
            pass
        # restaura próximo valor
        try:
            self.where_input.setPlainText(next_val)
        except Exception:
            pass
        # atualiza botões conforme ainda houver histórico/redo
        try:
            self.btn_undo_where.setEnabled(bool(getattr(self, '_where_history', [])))
            self.btn_redo_where.setEnabled(bool(getattr(self, '_where_redo', [])))
        except Exception:
            pass
    def _clear_param_filters(self):
        """Limpa todos os filtros parametrizados."""
        try:
            if not self._param_filters:
                return
            reply = QMessageBox.question(self, "Confirmação", "Remover todos os filtros parametrizados?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
            self._param_filters = []
            self._refresh_filters_list()
            try:
                if getattr(self, 'session_logger', None):
                    self.session_logger.log('clear_filters', 'Limpou filtros parametrizados')
            except Exception:
                pass
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao limpar filtros:\n{e}")

    def set_query_mode(self, mode: str):
        """Define o modo de consulta e habilita/desabilita controles relevantes.

        mode: 'metadados' ou 'manual'
        """
        try:
            mode = mode if mode in ('metadados', 'manual') else 'metadados'
            self.modo_consulta = mode
            is_meta = (mode == 'metadados')

            # =========================
            # 🔁 CONTROLE DE VISIBILIDADE DOS PAINÉIS
            # =========================
            try:
                if hasattr(self, '_predefined_panel'):
                    self._predefined_panel.setVisible(is_meta)
                if hasattr(self, '_manual_panel'):
                    self._manual_panel.setVisible(not is_meta)
            except Exception:
                pass

            # =========================
            # módulos/agrupamentos (somente metadados)
            # =========================
            try:
                if hasattr(self, 'combo_modulo') and self.combo_modulo is not None:
                    self.combo_modulo.setEnabled(is_meta)
                if hasattr(self, 'combo_agrupamento') and self.combo_agrupamento is not None:
                    self.combo_agrupamento.setEnabled(is_meta)
            except Exception:
                pass

            # =========================
            # controles da consulta manual
            # =========================
            try:
                self.tables_list.setEnabled(not is_meta)
                self.columns_list.setEnabled(not is_meta)
                self.selected_tables_list.setEnabled(not is_meta)
                self.selected_columns_list.setEnabled(not is_meta)

                try:
                    if hasattr(self, 'btn_remove_table'):
                        self.btn_remove_table.setEnabled(not is_meta)
                    if hasattr(self, 'btn_clear_tables'):
                        self.btn_clear_tables.setEnabled(not is_meta)
                    if hasattr(self, 'btn_add_tables'):
                        self.btn_add_tables.setEnabled(not is_meta)
                    if hasattr(self, 'btn_select_all'):
                        self.btn_select_all.setEnabled(not is_meta)
                    if hasattr(self, 'btn_deselect_all'):
                        self.btn_deselect_all.setEnabled(not is_meta)
                    if hasattr(self, 'btn_add_columns'):
                        self.btn_add_columns.setEnabled(not is_meta)
                    if hasattr(self, 'table_search'):
                        self.table_search.setEnabled(not is_meta)
                    if hasattr(self, 'column_search'):
                        self.column_search.setEnabled(not is_meta)
                except Exception:
                    pass
                # Além de habilitar/desabilitar, controlar também a visibilidade
                # dos campos relacionados às fontes de dados: no modo 'metadados'
                # esses campos não devem aparecer no formulário (aparecem apenas
                # no modo manual).
                try:
                    visible = not is_meta
                    for name in ('table_search', 'tables_list', 'selected_tables_list', 'btn_remove_table', 'btn_clear_tables'):
                        try:
                            if hasattr(self, name):
                                getattr(self, name).setVisible(visible)
                        except Exception:
                            pass

                    # Também tentar esconder labels estáticos (se existirem) com
                    # os textos esperados para evitar que os títulos permaneçam.
                    try:
                        for lbl in self.findChildren(QLabel):
                            try:
                                txt = lbl.text() or ''
                                if any(k in txt for k in ("De onde vêm os dados", "Fontes de dados escolhidas", "📂 De onde", "📌 Fontes")):
                                    lbl.setVisible(visible)
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass
            except Exception:
                pass

            # =========================
            # sincroniza estado dos rádios (chamada programática)
            # =========================
            try:
                if hasattr(self, 'mode_meta_radio'):
                    self.mode_meta_radio.setChecked(is_meta)
                if hasattr(self, 'mode_manual_radio'):
                    self.mode_manual_radio.setChecked(not is_meta)
            except Exception:
                pass

            # =========================
            # hint visual de modo
            # =========================
            try:
                if hasattr(self, 'mode_hint_label'):
                    if is_meta:
                        self.mode_hint_label.setText('Modo: Metadados — consultas automáticas')
                        self.mode_hint_label.setStyleSheet('color: #1abc9c; font-weight: bold;')
                    else:
                        self.mode_hint_label.setText('Modo: Manual — selecione tabelas/colunas')
                        self.mode_hint_label.setStyleSheet('color: #f39c12; font-weight: bold;')
            except Exception:
                pass

            # =========================
            # destaque visual (pulse)
            # =========================
            try:
                border_color = '#1abc9c' if is_meta else '#f39c12'
                border_style = f'2px solid {border_color}'

                def apply_pulse(widget):
                    try:
                        if widget is None:
                            return
                        original = widget.styleSheet() or ''
                        widget.setStyleSheet(original + f'; border: {border_style};')
                        QTimer.singleShot(
                            400,
                            lambda: widget.setStyleSheet(original + f'; border: 1px solid {border_color};')
                        )
                        QTimer.singleShot(1400, lambda: widget.setStyleSheet(original))
                    except Exception:
                        pass

                if is_meta:
                    apply_pulse(getattr(self, 'combo_modulo', None))
                    apply_pulse(getattr(self, 'combo_agrupamento', None))
                else:
                    apply_pulse(getattr(self, 'tables_list', None))
                    apply_pulse(getattr(self, 'columns_list', None))
                    apply_pulse(getattr(self, 'selected_tables_list', None))
                    apply_pulse(getattr(self, 'selected_columns_list', None))
            except Exception:
                pass

            # =========================
            # limpeza ao alternar modo
            # =========================
            try:
                try:
                    self._param_filters = []
                except Exception:
                    pass

                try:
                    self._refresh_filters_list()
                except Exception:
                    pass

                try:
                    if hasattr(self, 'sql_preview'):
                        self.sql_preview.setPlainText('')
                    self.current_sql = None
                    self.current_sql_params = None
                except Exception:
                    pass

                try:
                    self.where_input.clear()
                except Exception:
                    pass

                try:
                    if hasattr(self, 'selected_tables_list'):
                        self.selected_tables_list.clear()
                    if hasattr(self, 'selected_columns_list'):
                        self.selected_columns_list.clear()
                except Exception:
                    pass

                try:
                    if is_meta and hasattr(self, 'combo_agrupamento'):
                        self.combo_agrupamento.blockSignals(True)
                        self.combo_agrupamento.setCurrentIndex(0)
                        self.combo_agrupamento.blockSignals(False)
                except Exception:
                    pass
            except Exception:
                pass

            # força atualização visual
            try:
                self.updateGeometry()
            except Exception:
                pass

        except Exception:
            pass

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
            # Prefer executing the parameterized SQL stored in `self.current_sql`.
            # The preview (`self.sql_preview`) may have had '?' substituted for legibility
            # and thus not contain parameter markers while `self.current_sql_params` is set.
            exec_sql = getattr(self, 'current_sql', None) or sql
            params = getattr(self, 'current_sql_params', None)
            # If exec_sql appears to contain no parameter markers, but params is set, avoid
            # passing params to the driver (prevents '0 parameter markers, but N supplied').
            if params and '?' not in exec_sql:
                # fallback: try executing current_sql (if different) otherwise drop params
                if exec_sql is not sql and '?' in sql:
                    exec_sql = sql
                else:
                    # driver would raise; safer to clear params so call executes the literal SQL
                    params = None

            # Execute the query in a worker thread to keep the UI responsive and
            # show a progress dialog / timer while the query runs.
            progress = QProgressDialog("Executando consulta...", None, 0, 0, self)
            progress.setWindowTitle("Executando")
            progress.setWindowModality(Qt.ApplicationModal)
            try:
                progress.setCancelButton(None)
            except Exception:
                pass
            progress.setMinimumDuration(0)
            progress.show()
            QApplication.processEvents()

            class _QueryWorker(QThread):
                finished_signal = pyqtSignal(list, list)
                error_signal = pyqtSignal(str)

                def __init__(self, qb, sql, params):
                    super().__init__()
                    self._qb = qb
                    self._sql = sql
                    self._params = params

                def run(self):
                    try:
                        cols, rows = self._qb.execute_query(self._sql, self._params)
                        self.finished_signal.emit(cols, rows)
                    except Exception as exc:
                        self.error_signal.emit(str(exc))

            worker = _QueryWorker(self.qb, exec_sql, params)

            def _on_worker_finished(cols, rows):
                try:
                    if getattr(self, 'session_logger', None):
                        try:
                            self.session_logger.log('execute_query_success', f'Retorno {len(rows)} registros', {'rows': len(rows)})
                        except Exception:
                            pass
                    progress.close()
                except Exception:
                    pass
                try:
                    self.query_executed.emit(cols, rows)
                except Exception:
                    pass
                try:
                    QMessageBox.information(self, "Sucesso", f"Consulta executada com sucesso!\n{len(rows)} registros retornados.")
                except Exception:
                    pass
                try:
                    worker.deleteLater()
                except Exception:
                    pass

            def _on_worker_error(msg):
                try:
                    progress.close()
                except Exception:
                    pass
                QMessageBox.critical(self, "Erro", f"Erro ao executar consulta:\n{msg}")
                try:
                    worker.deleteLater()
                except Exception:
                    pass

            worker.finished_signal.connect(_on_worker_finished)
            worker.error_signal.connect(_on_worker_error)
            worker.start()
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
        main_layout = QVBoxLayout(self)

        # ===== Abas =====
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # =========================================================
        # ABA 1 — CONSTRUTOR DE CONSULTAS
        # =========================================================
        aba_consultas = QWidget()
        self.tabs.addTab(aba_consultas, "Construtor de Consultas")

        aba_layout = QHBoxLayout(aba_consultas)

        splitter_principal = QSplitter(Qt.Horizontal)
        aba_layout.addWidget(splitter_principal)

        # =========================================================
        # COLUNA ESQUERDA — Fontes de dados
        # =========================================================
        col_esq = QWidget()
        col_esq_layout = QVBoxLayout(col_esq)
        col_esq_layout.setContentsMargins(4, 4, 4, 4)

        col_esq_layout.addWidget(self.lbl_fontes)
        col_esq_layout.addWidget(self.txt_pesquisar_fontes)
        col_esq_layout.addWidget(self.lst_fontes)

        col_esq_layout.addWidget(self.lbl_fontes_escolhidas)
        col_esq_layout.addWidget(self.lst_fontes_escolhidas)

        col_esq_layout.addWidget(self.btn_remover_fonte)
        col_esq_layout.addWidget(self.btn_limpar_tudo)

        splitter_principal.addWidget(col_esq)

        # =========================================================
        # COLUNA CENTRAL — Informações + Módulo + Filtros
        # =========================================================
        col_centro = QWidget()
        col_centro_layout = QVBoxLayout(col_centro)
        col_centro_layout.setContentsMargins(4, 4, 4, 4)

        col_centro_layout.addWidget(self.lbl_info_disp)
        col_centro_layout.addWidget(self.txt_pesquisar_info)
        col_centro_layout.addWidget(self.lst_info_disp)

        btns_info = QHBoxLayout()
        btns_info.addWidget(self.btn_marcar_todas)
        btns_info.addWidget(self.btn_desmarcar_todas)
        col_centro_layout.addLayout(btns_info)

        col_centro_layout.addWidget(self.btn_adicionar_info)
        col_centro_layout.addWidget(self.lbl_info_relatorio)
        col_centro_layout.addWidget(self.lst_info_relatorio)
        col_centro_layout.addWidget(self.btn_remover_info)

        col_centro_layout.addSpacing(8)

        col_centro_layout.addWidget(self.lbl_modulo)
        col_centro_layout.addWidget(self.combo_modulo)

        col_centro_layout.addWidget(self.lbl_filtros)
        col_centro_layout.addWidget(self.grp_filtros_rapidos)
        col_centro_layout.addWidget(self.grp_gerenciar_filtros)

        splitter_principal.addWidget(col_centro)

        # =========================================================
        # COLUNA DIREITA — SQL + Ações
        # =========================================================
        col_dir = QWidget()
        col_dir_layout = QVBoxLayout(col_dir)
        col_dir_layout.setContentsMargins(4, 4, 4, 4)

        col_dir_layout.addWidget(self.lbl_modo_consulta)
        col_dir_layout.addWidget(self.combo_relacionamento)

        col_dir_layout.addWidget(self.lbl_sql)
        col_dir_layout.addWidget(self.txt_sql)

        col_dir_layout.addStretch()

        col_dir_layout.addWidget(self.btn_gerar_consulta)
        col_dir_layout.addWidget(self.btn_executar_consulta)
        col_dir_layout.addWidget(self.btn_salvar_consulta)
        col_dir_layout.addWidget(self.btn_carregar_consulta)
        col_dir_layout.addWidget(self.btn_excluir_consulta)
        col_dir_layout.addWidget(self.btn_gerenciar_consultas)

        splitter_principal.addWidget(col_dir)

        # =========================================================
        # Proporções (imagem 1)
        # =========================================================
        splitter_principal.setStretchFactor(0, 2)  # esquerda
        splitter_principal.setStretchFactor(1, 4)  # centro
        splitter_principal.setStretchFactor(2, 2)  # direita

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
                            date_fmt = getattr(main, 'date_format', '%m-%d-%Y')
                        except Exception:
                            date_fmt = '%m-%d-%Y'

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
                    date_format=getattr(self, 'date_format', '%m-%d-%Y'),
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
            date_fmt = getattr(main, 'date_format', '%m-%d-%Y')
            decimals = int(getattr(main, 'number_decimals', 2))
        except Exception:
            date_fmt = '%m-%d-%Y'
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

    def __init__(self, parent=None, date_format='%m-%d-%Y', number_decimals=2):
        super().__init__(parent)
        self.setWindowTitle('Preferências')
        self.date_format = date_format
        self.number_decimals = number_decimals
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel('Formato de data:'))
        self.date_combo = QComboBox()
        self.date_combo.addItem('MM-DD-YYYY', '%m-%d-%Y')
        self.date_combo.addItem('YYYY-MM-DD', '%Y-%m-%d')
        self.date_combo.addItem('DD/MM/YYYY', '%d/%m/%Y')
        # set current
        if self.date_format == '%m-%d-%Y':
            idx = 0
        elif self.date_format == '%Y-%m-%d':
            idx = 1
        else:
            idx = 2
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
            # Após estabelecer conexão, obtém informações do servidor SQL para exibir no rodapé
            try:
                sql_info = None
                cur = self.conn.cursor()
                try:
                    cur.execute(
                        """
                        SELECT
                            SERVERPROPERTY('ProductVersion') AS Versao,
                            SERVERPROPERTY('ProductLevel')   AS ServicePack,
                            SERVERPROPERTY('Edition')        AS Edicao,
                            @@SERVERNAME                     AS InstanceName,
                            DB_NAME()                        AS DatabaseName
                        """
                    )
                    row = cur.fetchone()
                    if row:
                        versao = row[0] or ''
                        servicepack = row[1] or ''
                        edicao = row[2] or ''
                        instance = row[3] or ''
                        dbname = row[4] or (self.db_config.db_name if getattr(self, 'db_config', None) else '')
                        sql_info = (
                            f"Microsoft SQL Server versão {versao} | Service Pack {servicepack} | "
                            f"Versão {edicao} | Instância: {str(instance).upper()} | Banco de dados: {dbname}"
                        )
                finally:
                    try:
                        cur.close()
                    except Exception:
                        pass
                # armazena para que o setup_ui possa usar ao criar o label
                self._sql_info_str = sql_info
            except Exception:
                logging.exception("Erro obtendo informações do servidor SQL durante a conexão")
        except Exception as e:
            # Log detalhado no terminal para debug
            logging.exception("Erro ao conectar ao banco")
            QMessageBox.critical(self, "Erro", f"Erro ao conectar ao banco:\n{str(e)}")
            sys.exit(1)
    
    def setup_ui(self):
        """Configura a interface"""
        # título contém nome do app + versão, seguido por nome da empresa e usuário logado
        user_name = self.user_data.get('NomeUsuario') if self.user_data else ''
        self.setWindowTitle(f"{APP_NAME} v{Version.get_version()} — {COMPANY_NAME} | {user_name}")
        self.setMinimumSize(1200, 800)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        
        # Barra de informações
        #info_bar = QHBoxLayout()
        #info_bar.addWidget(QLabel(f"<b>Usuário:</b> {self.user_data['NomeUsuario']}"))
        #info_bar.addWidget(QLabel(f"<b>Banco:</b> {self.db_config.db_name}"))
        #info_bar.addWidget(QLabel(f"<b>Servidor:</b> {self.db_config.server_name}"))
        #info_bar.addStretch()
        #layout.addLayout(info_bar)
        
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

        # Expor tabs como atributo para acesso robusto por callbacks externos
        self.tabs = tabs
        
        # Conecta sinais
        self.query_tab.query_executed.connect(self.on_query_executed)
        
        layout.addWidget(tabs)
        
        central_widget.setLayout(layout)
        
        # Menu
        self.create_menus()
        
        # Status bar
        # Mensagem pronta e label centralizado com o nome da empresa no rodapé
        self.statusBar().showMessage("Pronto")
        try:
            # cria um QLabel centralizado com as informações do SQL no rodapé
            try:
                self.sql_info_label = QLabel(getattr(self, '_sql_info_str', '') or "")
                self.sql_info_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                self.sql_info_label.setStyleSheet("color: #333; padding:2px 6px; font-size:11px;")
                # adiciona como permanent widget com stretch para ocupar o centro do rodapé
                self.statusBar().addPermanentWidget(self.sql_info_label, 1)
            except Exception:
                logging.exception("Erro criando label de informações do SQL no rodapé")
        except Exception:
            # Em caso de qualquer erro ao configurar o rodapé, não bloqueia a UI principal
            logging.exception("Erro configurando o rodapé")
    
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
        # Muda para aba de resultados - usa self.tabs quando disponível para evitar
        # acessar diretamente a estrutura do layout (que pode ter mudado).
        try:
            if hasattr(self, 'tabs') and self.tabs is not None:
                # aba 1 = Construtor, aba 2 = Resultados
                try:
                    self.tabs.setCurrentIndex(1)
                except Exception:
                    pass
            else:
                # fallback: tentar encontrar QTabWidget no centralWidget
                try:
                    tw = self.centralWidget().findChild(QTabWidget)
                    if tw is not None:
                        tw.setCurrentIndex(1)
                except Exception:
                    pass
        except Exception:
            pass
    
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
    # Abrir maximizado por solicitação do usuário
    window.showMaximized()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()