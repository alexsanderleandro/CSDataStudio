"""
Integração com OpenAI para geração de insights
"""
from typing import List, Tuple, Optional
import pandas as pd

class AIInsightsGenerator:
    """Gerador de insights usando OpenAI"""
    
    def __init__(self, api_key: str = None):
        """
        Inicializa o gerador de insights.
        
        Args:
            api_key: Chave da API OpenAI
        """
        self.api_key = api_key
        self._client = None
        
        if api_key:
            self._initialize_client()
    
    def _initialize_client(self):
        """Inicializa o cliente OpenAI"""
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "Biblioteca 'openai' não instalada. "
                "Instale com: pip install openai"
            )
        except Exception as e:
            print(f"Erro ao inicializar cliente OpenAI: {e}")
            self._client = None
    
    def set_api_key(self, api_key: str):
        """Define a chave da API"""
        self.api_key = api_key
        self._initialize_client()
    
    def generate_insights(
        self,
        data: List[Tuple],
        columns: List[str],
        query_description: str = None,
        max_rows_sample: int = 100
    ) -> str:
        """
        Gera insights sobre os dados usando IA.
        
        Args:
            data: Lista de tuplas com os dados
            columns: Nomes das colunas
            query_description: Descrição da consulta/contexto
            max_rows_sample: Número máximo de linhas para análise
        
        Returns:
            Texto com os insights gerados
        """
        if not self._client:
            return "Erro: Cliente OpenAI não inicializado. Configure a chave da API."
        
        try:
            # Converte dados para DataFrame
            df = pd.DataFrame(data, columns=columns)
            
            # Limita número de linhas para análise
            df_sample = df.head(max_rows_sample)
            
            # Gera estatísticas descritivas
            stats = self._generate_statistics(df)
            
            # Prepara prompt para a IA
            prompt = self._build_prompt(df_sample, stats, query_description)
            
            # Chama OpenAI
            response = self._client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Você é um analista de dados experiente. "
                            "Sua tarefa é analisar conjuntos de dados e fornecer insights "
                            "valiosos, padrões, tendências e recomendações em português do Brasil."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            insights = response.choices[0].message.content
            return insights
            
        except Exception as e:
            return f"Erro ao gerar insights: {str(e)}"
    
    def _generate_statistics(self, df: pd.DataFrame) -> dict:
        """Gera estatísticas descritivas dos dados"""
        stats = {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'columns': list(df.columns),
            'dtypes': df.dtypes.astype(str).to_dict(),
            'null_counts': df.isnull().sum().to_dict(),
            'numeric_stats': {}
        }
        
        # Estatísticas para colunas numéricas
        numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
        for col in numeric_cols:
            stats['numeric_stats'][col] = {
                'mean': float(df[col].mean()),
                'median': float(df[col].median()),
                'std': float(df[col].std()),
                'min': float(df[col].min()),
                'max': float(df[col].max())
            }
        
        return stats
    
    def _build_prompt(
        self,
        df: pd.DataFrame,
        stats: dict,
        query_description: str = None
    ) -> str:
        """Constrói o prompt para a IA"""
        
        # Primeiras linhas dos dados
        data_preview = df.head(10).to_string()
        
        prompt = f"""Analise o seguinte conjunto de dados e forneça insights detalhados:

CONTEXTO DA CONSULTA:
{query_description or 'Análise exploratória de dados'}

ESTATÍSTICAS GERAIS:
- Total de registros: {stats['total_rows']}
- Total de colunas: {stats['total_columns']}
- Colunas: {', '.join(stats['columns'])}

PREVIEW DOS DADOS (primeiras 10 linhas):
{data_preview}

ESTATÍSTICAS NUMÉRICAS:
{self._format_numeric_stats(stats['numeric_stats'])}

Por favor, forneça:
1. Uma análise geral dos dados
2. Padrões e tendências identificados
3. Valores atípicos ou anomalias, se houver
4. Correlações interessantes entre variáveis
5. Recomendações e próximos passos para análise
6. Insights de negócio relevantes

Formate a resposta de forma clara e estruturada em português do Brasil."""
        
        return prompt
    
    def _format_numeric_stats(self, numeric_stats: dict) -> str:
        """Formata estatísticas numéricas para o prompt"""
        if not numeric_stats:
            return "Nenhuma coluna numérica encontrada."
        
        lines = []
        for col, stats in numeric_stats.items():
            lines.append(f"\n{col}:")
            lines.append(f"  - Média: {stats['mean']:.2f}")
            lines.append(f"  - Mediana: {stats['median']:.2f}")
            lines.append(f"  - Desvio Padrão: {stats['std']:.2f}")
            lines.append(f"  - Mín: {stats['min']:.2f}, Máx: {stats['max']:.2f}")
        
        return '\n'.join(lines)
    
    def generate_custom_analysis(
        self,
        data: List[Tuple],
        columns: List[str],
        custom_question: str
    ) -> str:
        """
        Gera análise customizada baseada em uma pergunta específica.
        
        Args:
            data: Lista de tuplas com os dados
            columns: Nomes das colunas
            custom_question: Pergunta específica sobre os dados
        
        Returns:
            Resposta da IA
        """
        if not self._client:
            return "Erro: Cliente OpenAI não inicializado."
        
        try:
            df = pd.DataFrame(data, columns=columns)
            df_sample = df.head(50)
            
            data_preview = df_sample.to_string()
            
            prompt = f"""Com base nos seguintes dados:

{data_preview}

Responda à seguinte pergunta:
{custom_question}

Forneça uma resposta detalhada e fundamentada nos dados apresentados."""
            
            response = self._client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "Você é um analista de dados especializado."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Erro ao gerar análise: {str(e)}"

__all__ = ['AIInsightsGenerator']