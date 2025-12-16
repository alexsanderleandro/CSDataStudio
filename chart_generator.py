"""
Gerador de gráficos para CSData Studio
Suporta gráficos de barras e colunas com agregações
"""
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from typing import List, Tuple, Dict
from enum import Enum
import pandas as pd

class ChartType(Enum):
    """Tipos de gráficos suportados"""
    BAR = "bar"
    COLUMN = "column"

class AggregationType(Enum):
    """Tipos de agregação"""
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"

class ChartGenerator:
    """Gerador de gráficos usando matplotlib"""
    
    def __init__(self):
        # Configura estilo padrão
        plt.style.use('seaborn-v0_8-darkgrid')
        
    def create_chart(
        self,
        data: List[Tuple],
        columns: List[str],
        x_column: str,
        y_column: str,
        aggregation: AggregationType,
        chart_type: ChartType = ChartType.COLUMN,
        title: str = "Gráfico",
        x_label: str = None,
        y_label: str = None,
        color: str = '#3498db'
    ) -> Figure:
        """
        Cria um gráfico baseado nos dados fornecidos.
        
        Args:
            data: Lista de tuplas com os dados
            columns: Nomes das colunas
            x_column: Nome da coluna para eixo X
            y_column: Nome da coluna para eixo Y (será agregada)
            aggregation: Tipo de agregação (COUNT, SUM, etc)
            chart_type: Tipo de gráfico (BAR ou COLUMN)
            title: Título do gráfico
            x_label: Rótulo do eixo X (opcional)
            y_label: Rótulo do eixo Y (opcional)
            color: Cor das barras/colunas
        
        Returns:
            Figura matplotlib
        """
        try:
            # Converte dados para DataFrame
            df = pd.DataFrame(data, columns=columns)
            
            # Valida colunas
            if x_column not in df.columns:
                raise ValueError(f"Coluna '{x_column}' não encontrada")
            if y_column not in df.columns:
                raise ValueError(f"Coluna '{y_column}' não encontrada")
            
            # Aplica agregação
            if aggregation == AggregationType.COUNT:
                agg_data = df.groupby(x_column)[y_column].count()
                default_y_label = f"Contagem de {y_column}"
            elif aggregation == AggregationType.SUM:
                agg_data = df.groupby(x_column)[y_column].sum()
                default_y_label = f"Soma de {y_column}"
            elif aggregation == AggregationType.AVG:
                agg_data = df.groupby(x_column)[y_column].mean()
                default_y_label = f"Média de {y_column}"
            elif aggregation == AggregationType.MIN:
                agg_data = df.groupby(x_column)[y_column].min()
                default_y_label = f"Mínimo de {y_column}"
            elif aggregation == AggregationType.MAX:
                agg_data = df.groupby(x_column)[y_column].max()
                default_y_label = f"Máximo de {y_column}"
            else:
                raise ValueError(f"Tipo de agregação inválido: {aggregation}")
            
            # Cria figura
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # Desenha gráfico
            if chart_type == ChartType.BAR:
                # Gráfico de barras (horizontal)
                agg_data.plot(kind='barh', ax=ax, color=color)
            else:
                # Gráfico de colunas (vertical)
                agg_data.plot(kind='bar', ax=ax, color=color)
            
            # Configurações
            ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel(x_label or x_column, fontsize=12, fontweight='bold')
            ax.set_ylabel(y_label or default_y_label, fontsize=12, fontweight='bold')
            
            # Rotaciona labels do eixo X se necessário
            if chart_type == ChartType.COLUMN:
                plt.xticks(rotation=45, ha='right')
            
            # Adiciona valores nas barras/colunas
            for container in ax.containers:
                ax.bar_label(container, fmt='%.0f', padding=3)
            
            # Grid
            ax.grid(True, alpha=0.3, linestyle='--')
            
            # Ajusta layout
            plt.tight_layout()
            
            return fig
            
        except Exception as e:
            print(f"Erro ao criar gráfico: {e}")
            raise
    
    def create_multi_series_chart(
        self,
        data: List[Tuple],
        columns: List[str],
        x_column: str,
        y_columns: List[str],
        chart_type: ChartType = ChartType.COLUMN,
        title: str = "Gráfico Múltiplas Séries",
        x_label: str = None,
        y_label: str = None
    ) -> Figure:
        """
        Cria um gráfico com múltiplas séries de dados.
        
        Args:
            data: Lista de tuplas com os dados
            columns: Nomes das colunas
            x_column: Nome da coluna para eixo X
            y_columns: Lista de nomes das colunas para eixo Y
            chart_type: Tipo de gráfico
            title: Título do gráfico
            x_label: Rótulo do eixo X
            y_label: Rótulo do eixo Y
        
        Returns:
            Figura matplotlib
        """
        try:
            # Converte dados para DataFrame
            df = pd.DataFrame(data, columns=columns)
            
            # Valida colunas
            if x_column not in df.columns:
                raise ValueError(f"Coluna '{x_column}' não encontrada")
            for col in y_columns:
                if col not in df.columns:
                    raise ValueError(f"Coluna '{col}' não encontrada")
            
            # Prepara dados
            df_plot = df.set_index(x_column)[y_columns]
            
            # Cria figura
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # Desenha gráfico
            if chart_type == ChartType.BAR:
                df_plot.plot(kind='barh', ax=ax)
            else:
                df_plot.plot(kind='bar', ax=ax)
            
            # Configurações
            ax.set_title(title, fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel(x_label or x_column, fontsize=12, fontweight='bold')
            ax.set_ylabel(y_label or "Valores", fontsize=12, fontweight='bold')
            
            # Rotaciona labels
            if chart_type == ChartType.COLUMN:
                plt.xticks(rotation=45, ha='right')
            
            # Legenda
            ax.legend(title="Séries", loc='best')
            
            # Grid
            ax.grid(True, alpha=0.3, linestyle='--')
            
            # Ajusta layout
            plt.tight_layout()
            
            return fig
            
        except Exception as e:
            print(f"Erro ao criar gráfico múltiplas séries: {e}")
            raise
    
    @staticmethod
    def save_chart(fig: Figure, output_path: str, dpi: int = 150) -> bool:
        """Salva o gráfico em arquivo"""
        try:
            fig.savefig(output_path, dpi=dpi, bbox_inches='tight')
            return True
        except Exception as e:
            print(f"Erro ao salvar gráfico: {e}")
            return False

__all__ = ['ChartGenerator', 'ChartType', 'AggregationType']