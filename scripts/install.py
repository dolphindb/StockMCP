"""Idempotent stock MCP installation; never drops user databases."""
import json
import os
import re
from pathlib import Path
from common import ROOT, TABLES, connect, literal


def install(session):
    # Check legacy financial keys before changing any objects. Old LAST keys have
    # already collapsed distinct statements; a reimport into new tables is required.
    for table in ['quarter_stock_income','quarter_stock_balancesheet','quarter_stock_cashflow']:
        if session.run(f'existsTable("dfs://quarter_factor",{literal(table)})'):
            keys=set(session.run(f'schema(loadTable("dfs://quarter_factor",{literal(table)})).sortColumns'))
            if not {'ts_code','report_type','end_date','f_ann_date','ann_date'} <= keys:
                raise RuntimeError(f'{table}: legacy financial key; use a fresh instance and reimport (see docs/local_deployment.md). Existing data has not been deleted.')
    if session.run('existsTable("dfs://day_factor","index_daily")'):
        if session.run('schema(loadTable("dfs://day_factor","index_daily")).keepDuplicates') != 'LAST':
            raise RuntimeError('index_daily: legacy ALL duplicate policy; use a fresh instance and reimport (see docs/local_deployment.md).')
    schema = (ROOT / '建库建表/ddl.dos').read_text()
    module_dir = session.run('getHomeDir()') + '/modules/DolphinDBModules/EasyTushare'
    session.run(f'if (!exists({literal(module_dir)})) mkdir({literal(module_dir)})')
    for filename, content in [
        ('createDBTB.dos', schema),
        ('utils.dos', (ROOT / 'modules/DolphinDBModules/EasyTushare/utils.dos').read_text()),
    ]:
        session.upload({'stockmcpFileText': content})
        session.run(f'f=file({literal(module_dir+"/"+filename)}, "w"); f.writeBytes(toCharArray(stockmcpFileText)); f.close()')
    session.run(re.sub(r'^module .*\n', '', schema, count=1))
    session.run('createDB()')
    for function, _, _ in TABLES:
        session.run(function + '()')
    session.run((ROOT / 'scripts/bootstrap.dos').read_text())
    mapping = {name: path.removeprefix('dfs://') for _, path, name in TABLES}
    # Persist a function view: each importer opens an independent session.
    function = 'def getDBname(tbName){ m=' + literal(mapping) + '; if (!(tbName in m.keys())) throw "Unknown table: " + tbName; return m[tbName] }'
    session.run(function)
    session.run('try {dropFunctionView("getDBname")} catch(ex){}; addFunctionView(getDBname)')
    session.run((ROOT / 'scripts/runtime.dos').read_text())
    export_url = os.getenv('STOCKMCP_EXPORT_URL', '').rstrip('/')
    # Do not erase a configured URL on repeated installs unless explicitly supplied.
    if 'STOCKMCP_EXPORT_URL' in os.environ:
        session.run(f'upsert!(loadTable("dfs://config","stockmcp_settings"),table(["export_url"] as name,[{literal(export_url)}] as value),keyColNames=`name)')
    from factors import metadata_frame
    from common import append_frame
    append_frame(session, 'dfs://factor_meta', 'factor_meta', metadata_frame())
    # Export helper is a dependency of the factor evaluation tool.
    files = sorted((ROOT / 'MCP_Tools').glob('*.dos'), key=lambda f: (f.stem != 'export_table_to_csv', f.name))
    for file in files:
        session.run(file.read_text())
        print('Published:', file.stem)
    expected = {f.stem for f in files}
    actual = set(session.run('exec name from listMCPTools()'))
    if not expected <= actual:
        raise RuntimeError('Missing tools: ' + str(expected - actual))
    print(f'Installed {len(expected)} tools; existing data preserved.')

if __name__ == '__main__':
    s = connect()
    try:
        install(s)
    finally:
        s.close()
