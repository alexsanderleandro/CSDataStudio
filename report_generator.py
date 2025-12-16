"""
Gerador de relatórios em PDF para CSData Studio
Suporta tabelas, gráficos e insights de IA
"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
from typing import List, Tuple, Optional
import io
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

class ReportGenerator:
    """Gerador de relatórios em PDF"""
    
    # Texto fixo LGPD no rodapé
    LGPD_TEXT = (
        "Este relatório contém dados pessoais protegidos pela Lei n.º 13.709/18, "
        "cuja captação se deu de modo expressamente consentido, portanto, o acesso de qualquer pessoa sem "
        "autorização a este documento configurará violação legal, sujeitando o autor do fato à "
        "responsabilização civil e penal."
    )
    
    def __init__(
        self,
        company_name: str = "CEO Software",
        app_name: str = "CSData Studio",
        app_version: str = "25.01.15 rev.1"
    ):
        self.company_name = company_name
        self.app_name = app_name
        self.app_version = app_version
    
    def create_report(
        self,
        output_path: str,
        report_name: str,
        user_name: str,
        orientation: str = 'portrait',  # 'portrait' ou 'landscape'
        include_insights: bool = False,
        insights_text: str = None,
        include_chart: bool = False,
        chart_figure: Figure = None,
        include_table: bool = True,
        columns: List[str] = None,
        data: List[Tuple] = None
    ) -> bool:
        """
        Cria um relatório PDF completo.
        
        Args:
            output_path: Caminho do arquivo PDF de saída
            report_name: Nome da pesquisa (obrigatório)
            user_name: Nome do usuário que gerou
            orientation: 'portrait' ou 'landscape'
            include_insights: Incluir seção de insights
            insights_text: Texto dos insights da IA
            include_chart: Incluir gráfico
            chart_figure: Figura matplotlib
            include_table: Incluir tabela de dados
            columns: Nomes das colunas
            data: Dados da tabela
        """
        try:
            # Define pagesize
            pagesize = landscape(A4) if orientation == 'landscape' else A4
            
            # Cria documento
            doc = SimpleDocTemplate(
                output_path,
                pagesize=pagesize,
                leftMargin=2*cm,
                rightMargin=2*cm,
                topMargin=3*cm,
                bottomMargin=3*cm
            )
            
            # Container para elementos
            story = []
            
            # Estilos
            styles = self._get_styles()
            
            # 1. Insights (se incluído)
            if include_insights and insights_text:
                story.append(Paragraph("Insights e Análise", styles['Heading1']))
                story.append(Spacer(1, 0.5*cm))
                
                # Divide insights em parágrafos
                for para in insights_text.split('\n\n'):
                    if para.strip():
                        story.append(Paragraph(para.strip(), styles['Normal']))
                        story.append(Spacer(1, 0.3*cm))
                
                story.append(Spacer(1, 1*cm))
            
            # 2. Gráfico (se incluído)
            if include_chart and chart_figure:
                story.append(Paragraph("Visualização de Dados", styles['Heading1']))
                story.append(Spacer(1, 0.5*cm))
                
                # Converte figura matplotlib para imagem
                img_buffer = io.BytesIO()
                chart_figure.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
                img_buffer.seek(0)
                
                # Adiciona imagem ao PDF
                img = Image(img_buffer, width=15*cm, height=10*cm)
                story.append(img)
                story.append(Spacer(1, 1*cm))
            
            # 3. Tabela de Resultados (se incluída)
            if include_table and columns and data:
                story.append(Paragraph("Resultado da Consulta", styles['Heading1']))
                story.append(Spacer(1, 0.5*cm))
                
                # Prepara dados da tabela
                table_data = [columns]  # Cabeçalho
                table_data.extend(data[:100])  # Limita a 100 linhas no PDF
                
                # Cria tabela
                table = Table(table_data, repeatRows=1)
                
                # Estilo da tabela
                table.setStyle(TableStyle([
                    # Cabeçalho
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    
                    # Corpo
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')])
                ]))
                
                story.append(table)
                
                if len(data) > 100:
                    story.append(Spacer(1, 0.5*cm))
                    story.append(Paragraph(
                        f"<i>Exibindo 100 de {len(data)} registros</i>",
                        styles['Italic']
                    ))
            
            # Constrói PDF com cabeçalho e rodapé
            doc.build(
                story,
                onFirstPage=lambda c, d: self._add_header_footer(c, d, report_name, user_name, True),
                onLaterPages=lambda c, d: self._add_header_footer(c, d, report_name, user_name, False)
            )
            
            return True
            
        except Exception as e:
            print(f"Erro ao gerar relatório: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_styles(self):
        """Define estilos para o documento"""
        styles = getSampleStyleSheet()
        
        # Customiza estilos existentes
        styles['Heading1'].fontSize = 16
        styles['Heading1'].textColor = colors.HexColor('#2C3E50')
        styles['Heading1'].spaceAfter = 12
        
        # Adiciona estilo itálico
        styles.add(ParagraphStyle(
            name='Italic',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=9,
            textColor=colors.grey
        ))
        
        return styles
    
    def _add_header_footer(
        self,
        canvas_obj: canvas.Canvas,
        doc,
        report_name: str,
        user_name: str,
        is_first_page: bool
    ):
        """Adiciona cabeçalho e rodapé a cada página"""
        canvas_obj.saveState()
        
        width, height = doc.pagesize
        
        # === CABEÇALHO ===
        # Empresa à esquerda
        canvas_obj.setFont('Helvetica-Bold', 12)
        canvas_obj.drawString(2*cm, height - 1.5*cm, self.company_name)
        
        # Informações à direita
        canvas_obj.setFont('Helvetica', 9)
        y_pos = height - 1.5*cm
        
        # Nome do aplicativo e versão
        text = f"{self.app_name} v{self.app_version}"
        canvas_obj.drawRightString(width - 2*cm, y_pos, text)
        
        # Nome da pesquisa
        y_pos -= 0.5*cm
        canvas_obj.setFont('Helvetica-Bold', 10)
        canvas_obj.drawRightString(width - 2*cm, y_pos, report_name)
        
        # Linha separadora
        canvas_obj.setStrokeColor(colors.HexColor('#2C3E50'))
        canvas_obj.setLineWidth(1)
        canvas_obj.line(2*cm, height - 2.2*cm, width - 2*cm, height - 2.2*cm)
        
        # === RODAPÉ ===
        # Linha separadora superior
        canvas_obj.line(2*cm, 2.5*cm, width - 2*cm, 2.5*cm)
        
        # Informações do rodapé
        canvas_obj.setFont('Helvetica', 8)
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        # Usuário e data à esquerda
        footer_text = f"Gerado por: {user_name} em {now}"
        canvas_obj.drawString(2*cm, 2.2*cm, footer_text)
        
        # Número da página à direita
        page_num = f"Página {doc.page}/{doc.page}"  # Será atualizado pelo reportlab
        canvas_obj.drawRightString(width - 2*cm, 2.2*cm, page_num)
        
        # Texto LGPD
        canvas_obj.setFont('Helvetica', 7)
        text_object = canvas_obj.beginText(2*cm, 1.8*cm)
        text_object.setFont('Helvetica', 7)
        
        # Quebra o texto LGPD em múltiplas linhas
        from textwrap import wrap
        max_width = int((width - 4*cm) / 0.2)  # Largura aproximada em caracteres
        lines = wrap(self.LGPD_TEXT, max_width)
        
        for line in lines:
            text_object.textLine(line)
        
        canvas_obj.drawText(text_object)
        
        canvas_obj.restoreState()

__all__ = ['ReportGenerator']