"""Compatibility adapter for the maintained importer."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from import_tushare import Importer
import dolphindb as ddb

def main(session,startDate,endDate,token,dataSource,maxRetries):
    s=ddb.session()
    if not s.connect(session['host'],session['port'],session['username'],session['password']):
        raise RuntimeError('DolphinDB connection failed')
    try:Importer(s,token,startDate,endDate).run(dataSource)
    finally:s.close()
