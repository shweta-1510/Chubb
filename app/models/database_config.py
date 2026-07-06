"""
Database configuration model for health checks.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseConfig:
    """Database connection configuration for health checks."""
    database_type: str  # PostgreSQL, MySQL, MSSQL
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    database_name: Optional[str] = "postgres"
    
    def __post_init__(self):
        """Validate database type."""
        valid_types = ["PostgreSQL", "MySQL", "MSSQL", "postgresql", "mysql", "mssql"]
        if self.database_type not in valid_types:
            raise ValueError(f"Invalid database type: {self.database_type}. Must be one of {valid_types}")
    
    @property
    def connection_string(self) -> str:
        """Generate connection string based on database type."""
        db_type = self.database_type.lower()
        
        if db_type in ["postgresql", "postgres"]:
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database_name}"
        elif db_type == "mysql":
            return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database_name}"
        elif db_type in ["mssql", "sqlserver"]:
            return f"mssql+pyodbc://{self.username}:{self.password}@{self.host}:{self.port}/{self.database_name}?driver=ODBC+Driver+17+for+SQL+Server"
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")
