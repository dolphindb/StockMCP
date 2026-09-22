"""Shared deployment connection and schema-aware dataframe ingestion."""
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
import dolphindb as ddb

ROOT = Path(__file__).resolve().parents[1]
TABLES = json.loads((ROOT / 'scripts/tables.json').read_text())
TABLE_PATHS = {table: database for _, database, table in TABLES}

def connect():
    password = os.getenv('DDB_PASSWORD')
    if not password:
        raise SystemExit('Set DDB_PASSWORD (see .env.example); no default password is assumed.')
    session = ddb.session()
    if not session.connect(os.getenv('DDB_HOST', '127.0.0.1'), int(os.getenv('DDB_PORT', '8848')),
                           os.getenv('DDB_USER', 'admin'), password):
        raise RuntimeError('DolphinDB connection failed')
    return session

def literal(value):
    return json.dumps(value, ensure_ascii=False)

def append_frame(session, database, table, frame):
    """Align by server schema, never by incidental upstream API column ordering."""
    if frame.empty:
        return 0
    schema = session.run(f'schema(loadTable({literal(database)}, {literal(table)})).colDefs')
    result = {}
    for row in schema.itertuples():
        name, dtype = row.name, row.typeString
        values = frame[name] if name in frame else pd.Series(index=frame.index, dtype='object')
        if dtype in ('DATE', 'TIMESTAMP', 'DATETIME', 'NANOTIMESTAMP'):
            if name == 'update_time' and name not in frame:
                values = pd.Series(pd.Timestamp.now(), index=frame.index)
            result[name] = pd.to_datetime(values, errors='coerce').astype('datetime64[ns]')
        elif dtype in ('DOUBLE', 'FLOAT', 'INT', 'LONG', 'SHORT'):
            result[name] = pd.to_numeric(values, errors='coerce').astype(float)
        else:
            result[name] = values.fillna('').astype(str)
    session.upload({'stockmcpUpload': pd.DataFrame(result).reset_index(drop=True)})
    # Cast on the server using authoritative column types, including null integer columns.
    expressions = ','.join(f'{row.typeString.lower()}(stockmcpUpload[{literal(row.name)}]) as {row.name}'
                           for row in schema.itertuples())
    if database == 'dfs://factor_meta':
        return session.run(f'upsert!(loadTable({literal(database)}, {literal(table)}),table({expressions}),keyColNames=`factor_name)')
    return session.run(f'loadTable({literal(database)}, {literal(table)}).append!(table({expressions}))')
