"""Reconciliation of the six-stock real-data acceptance fixture.

Requires DDB_* and TUSHARE_TOKEN; run after importing 20250901..20250912.
"""
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
from common import connect
from import_tushare import Importer


def main():
    s=connect()
    try:
        imp=Importer(s,os.environ['TUSHARE_TOKEN'],'20250901','20250912',['600519.SH'])
        upstream=imp.query('daily',ts_code='600519.SH',start_date=imp.start,end_date=imp.end)
        actual=s.run('select * from loadTable("dfs://day_factor","stock_daily") where ts_code="600519.SH"')
        actual['trade_date']=actual.trade_date.dt.strftime('%Y%m%d')
        both=actual.merge(upstream,on=['ts_code','trade_date'],suffixes=('_ddb','_api'),validate='one_to_one')
        assert len(both)==len(upstream)==10
        for col in ['open','high','low','close','pre_close','vol','amount']:
            np.testing.assert_allclose(both[col+'_ddb'],both[col+'_api'],rtol=1e-12)
        # Reimport the same API rows to verify the schema's LAST-key idempotence.
        imp.save('stock_daily',upstream)
        prices=s.run('select ts_code,trade_date,close from loadTable("dfs://day_factor","stock_daily")')
        assert len(prices)==60 and prices.ts_code.nunique()==6
        factors=s.run('select * from loadTable("dfs://factor","day_factor")')
        assert len(factors)==2040 and factors.factorname.nunique()==34
        pe=s.run('select ts_code,trade_date,pe from loadTable("dfs://day_factor","stock_daily_basic")')
        f=factors[factors.factorname=='pe'].rename(columns={'securityid':'ts_code','tradetime':'trade_date'})
        pair=pe.merge(f,on=['ts_code','trade_date'],validate='one_to_one')
        assert len(pair)==60
        np.testing.assert_allclose(pair.pe,pair.value,rtol=1e-12,equal_nan=True)
        financial={}
        for table in ['quarter_stock_income','quarter_stock_balancesheet','quarter_stock_cashflow']:
            frame=s.run(f'select * from loadTable("dfs://quarter_factor","{table}")')
            assert frame.ts_code.nunique()==6 and frame.end_date.notna().all()
            # Compare every upstream statement key, not just a nonempty response.
            keys=['ts_code','report_type','end_date','f_ann_date','ann_date']
            expected=[]
            for code in sorted(frame.ts_code.unique()):
                expected.append(imp.query(table.removeprefix('quarter_stock_'),ts_code=code,fields=','.join(keys)))
            expected=pd.concat(expected,ignore_index=True)
            def keyset(data):
                data=data[keys].copy()
                for col in ['end_date','f_ann_date','ann_date']:
                    data[col]=pd.to_datetime(data[col],errors='coerce').dt.strftime('%Y%m%d')
                return set(map(tuple,data.fillna('').astype(str).to_numpy()))
            assert keyset(frame)==keyset(expected), f'{table}: statement keys were lost or changed'
            assert len(frame)==len(keyset(expected)), f'{table}: duplicate keys'
            financial[table]=len(frame)
        valid={name:int(factors.loc[factors.factorname==name,'value'].notna().sum()) for name in ['ROE','net_profit_margin','debt_ratio','profit_yoy']}
        assert all(n>0 for n in valid.values()),valid
        report={'raw_price_rows':len(prices),'factor_rows':len(factors),'factor_names':34,
                'upstream_reconciled_rows':len(both),'upstream_reconciled_fields':7,
                'pe_reconciled_rows':len(pair),'financial_rows':financial,'valid_financial_factors':valid}
        Path('artifacts').mkdir(exist_ok=True)
        Path('artifacts/live_reconciliation.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
    finally:s.close()

if __name__=='__main__':main()
