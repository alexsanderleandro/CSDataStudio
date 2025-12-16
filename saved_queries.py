"""
Gerenciador de consultas salvas para CSData Studio
Salva, carrega e gerencia consultas personalizadas
"""
import json
import os
from typing import List, Optional, Dict
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class SavedQuery:
    """Representa uma consulta salva"""
    name: str
    sql: str
    description: str
    created_at: str
    modified_at: str
    created_by: str
    tags: List[str]
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @staticmethod
    def from_dict(data: Dict) -> 'SavedQuery':
        return SavedQuery(**data)

class QueryManager:
    """Gerencia consultas salvas em arquivo JSON"""
    
    def __init__(self, storage_path: str = None):
        if storage_path is None:
            # Pasta padrão do aplicativo
            app_data = os.path.join(
                os.environ.get('APPDATA', os.path.expanduser('~')),
                'CSDataStudio'
            )
            os.makedirs(app_data, exist_ok=True)
            storage_path = os.path.join(app_data, 'saved_queries.json')
        
        self.storage_path = storage_path
        self._queries: Dict[str, SavedQuery] = {}
        self.load_queries()
    
    def load_queries(self) -> bool:
        """Carrega consultas do arquivo"""
        try:
            if not os.path.exists(self.storage_path):
                self._queries = {}
                return True
            
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._queries = {}
            for name, query_data in data.items():
                self._queries[name] = SavedQuery.from_dict(query_data)
            
            return True
            
        except Exception as e:
            print(f"Erro ao carregar consultas: {e}")
            self._queries = {}
            return False
    
    def save_queries(self) -> bool:
        """Salva consultas no arquivo"""
        try:
            data = {name: query.to_dict() for name, query in self._queries.items()}
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Erro ao salvar consultas: {e}")
            return False
    
    def add_query(
        self,
        name: str,
        sql: str,
        description: str = "",
        created_by: str = "",
        tags: List[str] = None,
        overwrite: bool = False
    ) -> bool:
        """
        Adiciona uma nova consulta.
        
        Args:
            name: Nome único da consulta
            sql: Query SQL
            description: Descrição da consulta
            created_by: Nome do usuário que criou
            tags: Lista de tags para categorização
            overwrite: Se True, sobrescreve consulta existente
        
        Returns:
            True se adicionou com sucesso
        """
        if not name or not sql:
            raise ValueError("Nome e SQL são obrigatórios")
        
        if name in self._queries and not overwrite:
            raise ValueError(f"Consulta '{name}' já existe. Use overwrite=True para sobrescrever.")
        
        now = datetime.now().isoformat()
        
        if name in self._queries:
            # Atualiza consulta existente
            query = self._queries[name]
            query.sql = sql
            query.description = description
            query.modified_at = now
            query.tags = tags or []
        else:
            # Cria nova consulta
            query = SavedQuery(
                name=name,
                sql=sql,
                description=description,
                created_at=now,
                modified_at=now,
                created_by=created_by,
                tags=tags or []
            )
            self._queries[name] = query
        
        return self.save_queries()
    
    def get_query(self, name: str) -> Optional[SavedQuery]:
        """Retorna uma consulta pelo nome"""
        return self._queries.get(name)
    
    def delete_query(self, name: str) -> bool:
        """Remove uma consulta"""
        if name in self._queries:
            del self._queries[name]
            return self.save_queries()
        return False
    
    def list_queries(self, tag: str = None) -> List[SavedQuery]:
        """
        Lista todas as consultas, opcionalmente filtradas por tag.
        """
        queries = list(self._queries.values())
        
        if tag:
            queries = [q for q in queries if tag in q.tags]
        
        return sorted(queries, key=lambda q: q.modified_at, reverse=True)
    
    def search_queries(self, search_term: str) -> List[SavedQuery]:
        """
        Busca consultas por termo (nome, descrição ou SQL).
        """
        term = search_term.lower()
        results = []
        
        for query in self._queries.values():
            if (term in query.name.lower() or 
                term in query.description.lower() or 
                term in query.sql.lower()):
                results.append(query)
        
        return results
    
    def rename_query(self, old_name: str, new_name: str) -> bool:
        """Renomeia uma consulta"""
        if old_name not in self._queries:
            return False
        
        if new_name in self._queries and new_name != old_name:
            raise ValueError(f"Já existe uma consulta com o nome '{new_name}'")
        
        query = self._queries[old_name]
        query.name = new_name
        query.modified_at = datetime.now().isoformat()
        
        del self._queries[old_name]
        self._queries[new_name] = query
        
        return self.save_queries()
    
    def export_query_as_view(self, name: str, view_name: str = None) -> str:
        """
        Exporta uma consulta como CREATE VIEW para Power BI.
        """
        query = self.get_query(name)
        if not query:
            raise ValueError(f"Consulta '{name}' não encontrada")
        
        if not view_name:
            view_name = f"vw_{name.replace(' ', '_')}"
        
        view_sql = f"""-- View gerada pelo CSData Studio
-- Consulta: {query.name}
-- Descrição: {query.description}
-- Criado em: {query.created_at}

CREATE VIEW [dbo].[{view_name}] AS
{query.sql}
GO
"""
        return view_sql

__all__ = ['QueryManager', 'SavedQuery']