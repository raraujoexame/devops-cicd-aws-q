import os
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import BaseModel, Field


load_dotenv()  # Carrega .env, .env.development, etc., se existirem


def _get_env(name: str, default: Optional[str] = None) -> str:
    """Lê uma variável de ambiente e lança erro se não estiver definida (a menos que um default seja fornecido)."""
    value = os.getenv(name, default)

    if value is None:

        raise RuntimeError(f"Variavel de ambiente que é obrigatória não definida: {name}")
    
    return value + default if default else value


def build_connection_params() -> Dict[str, Any]:
    """
    Lê as variáveis de ambiente definidas no README e monta o dicionário de conexão.
    """
    return {
        "host": _get_env("POSTGRES_HOST", "localhost"),
        "port": int(_get_env("POSTGRES_PORT", "5432")),
        "user": _get_env("POSTGRES_USER"),
        "password": _get_env("POSTGRES_PASSWORD"),
        "dbname": _get_env("POSTGRES_DB"),
    }


@contextmanager
def get_connection():
    """
    Context manager simples para abrir/fechar conexão.
    Em cenários de maior carga, substitua por pool de conexões.
    """
    conn = psycopg2.connect(**build_connection_params())
    try:
        yield conn
    finally:
        conn.close()


app = FastMCP("postgresql-mcp-server")


class TopUsersByOrdersInput(BaseModel):
    days: int = Field(
        30,
        description=(
            "Janela em dias para considerar pedidos recentes. "
            "Ex.: 30 para últimos 30 dias."
        ),
        ge=1,
    )
    limit: int = Field(
        10,
        description="Quantidade máxima de usuários no ranking.",
        ge=1,
        le=1000,
    )


class QueryResultRow(BaseModel):
    columns: List[str]
    values: List[Any]


class QueryResult(BaseModel):
    row_count: int
    columns: List[str]
    rows: List[List[Any]]


class ExportToCsvInput(BaseModel):
    query: str = Field(description="Query SQL completa a ser executada.")
    filename: str = Field(
        description=(
            "Nome do arquivo CSV a ser gerado. "
            "Será criado no diretório de trabalho atual."
        )
    )


class ExecuteCustomQueryInput(BaseModel):
    query: str = Field(
        description=(
            "Query SQL a ser executada. "
            "Por segurança, apenas SELECT é permitido por padrão."
        )
    )
    allow_mutation: bool = Field(
        False,
        description=(
            "Se verdadeiro, permite comandos de escrita "
            "(INSERT/UPDATE/DELETE/DDL). Use com cuidado."
        ),
    )


class TableInfoInput(BaseModel):
    table_name: str = Field(description="Nome da tabela (schema.opcional_tabela).")


@app.tool()
def list_tables() -> List[str]:
    """
    Lista todas as tabelas do schema público do banco de dados.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_schema || '.' || table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name
                """
            )
            return [row[0] for row in cur.fetchall()]


@app.tool()
def get_table_info(input: TableInfoInput) -> Dict[str, Any]:
    """
    Retorna estrutura, tipos de dados e constraints de uma tabela.
    """
    table = input.table_name

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Colunas
            cur.execute(
                """
                SELECT
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_name = split_part(%s, '.', 2)
                  AND table_schema = COALESCE(NULLIF(split_part(%s, '.', 1), ''), 'public')
                ORDER BY ordinal_position
                """,
                (table, table),
            )
            columns = [
                {
                    "column_name": c[0],
                    "data_type": c[1],
                    "is_nullable": c[2],
                    "default": c[3],
                }
                for c in cur.fetchall()
            ]

            # Constraints
            cur.execute(
                """
                SELECT
                    tc.constraint_type,
                    kcu.column_name,
                    tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                 AND tc.table_name = kcu.table_name
                WHERE tc.table_name = split_part(%s, '.', 2)
                  AND tc.table_schema = COALESCE(NULLIF(split_part(%s, '.', 1), ''), 'public')
                """,
                (table, table),
            )
            constraints = [
                {
                    "type": r[0],
                    "column": r[1],
                    "name": r[2],
                }
                for r in cur.fetchall()
            ]

    return {
        "table": table,
        "columns": columns,
        "constraints": constraints,
    }


@app.tool()
def execute_custom_query(input: ExecuteCustomQueryInput) -> QueryResult:
    """
    Executa uma query SQL arbitrária.

    Por padrão, apenas SELECT é permitido. Para comandos de escrita,
    defina allow_mutation=True.
    """
    sql = input.query.strip()
    is_select = sql.lower().startswith("select")

    if not is_select and not input.allow_mutation:
        raise ValueError(
            "Apenas queries SELECT são permitidas por padrão. "
            "Defina allow_mutation=True para permitir comandos de escrita."
        )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)

            if is_select:
                rows = cur.fetchall()
                col_names = [desc[0] for desc in cur.description] if cur.description else []
                return QueryResult(
                    row_count=len(rows),
                    columns=col_names,
                    rows=[list(r) for r in rows],
                )
            else:
                affected = cur.rowcount
                conn.commit()
                return QueryResult(
                    row_count=affected,
                    columns=[],
                    rows=[],
                )


@app.tool()
def export_to_csv(input: ExportToCsvInput) -> Dict[str, Any]:
    """
    Executa uma query e exporta o resultado para um arquivo CSV.
    Retorna caminho do arquivo e quantidade de linhas exportadas.
    """
    sql = input.query
    filename = input.filename

    if not filename.lower().endswith(".csv"):
        filename = f"{filename}.csv"

    output_path = os.path.abspath(filename)

    with get_connection() as conn:
        df = pd.read_sql_query(sql, conn)
        df.to_csv(output_path, index=False)

    return {
        "csv_path": output_path,
        "row_count": int(df.shape[0]),
        "columns": list(df.columns),
    }


@app.tool()
def top_users_by_orders(input: TopUsersByOrdersInput) -> QueryResult:
    """
    Retorna um ranking de usuários com maior número de pedidos
    em uma janela de N dias.

    Espera uma tabela 'orders' com colunas:
      - user_id
      - created_at (timestamp)
    """
    sql = """
        SELECT
            user_id,
            COUNT(*) AS total_orders
        FROM orders
        WHERE created_at >= (CURRENT_DATE - INTERVAL '%s days')
        GROUP BY user_id
        ORDER BY total_orders DESC
        LIMIT %s
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (input.days, input.limit))
            rows = cur.fetchall()
            col_names = [desc[0] for desc in cur.description] if cur.description else []

    return QueryResult(
        row_count=len(rows),
        columns=col_names,
        rows=[list(r) for r in rows],
    )


if __name__ == "__main__":
    # Inicia o servidor MCP via HTTP em localhost:8000
    app.run(transport="http", host="127.0.0.1", port=8000)

