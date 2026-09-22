"""Explicit, sequential Tushare import with schema alignment and failure propagation."""
import argparse
import os
import time
import pandas as pd
from common import connect, append_frame, TABLE_PATHS, literal

INDEXES={'000300.SH':'hs300','000016.SH':'sz50','000852.SH':'csi1000'}
CORE=['stock_basic','stock_name','stock_daily','stock_adj_factor','stock_daily_basic','stock_limit',
      'stock_st','index_basic','index_daily','index_weight','quarter_stock_income',
      'quarter_stock_balancesheet','quarter_stock_cashflow','stock_daily_prev']

class Importer:
    def __init__(self,session,token,start,end,codes=None,pause=0.6):
        import tushare as ts
        self.s=session;self.pro=ts.pro_api(token);self.start=start;self.end=end
        self.codes=codes;self.pause=pause;self._dates=None
    def query(self,endpoint,**kwargs):
        # Pagination uses a deliberately small page and detects APIs ignoring offset.
        pages=[];offset=0;previous=None
        while True:
            for attempt in range(3):
                try:
                    time.sleep(self.pause)
                    data=self.pro.query(endpoint,limit=500,offset=offset,**kwargs)
                    break
                except Exception:
                    if attempt==2:raise
                    time.sleep(2**attempt)
            if data is None: raise RuntimeError(f'{endpoint} returned None')
            if data.empty:break
            signature=pd.util.hash_pandas_object(data,index=False).values.tobytes()
            if signature==previous:raise RuntimeError(f'{endpoint} ignored pagination offset; refusing truncated import')
            previous=signature;pages.append(data)
            if len(data)<500:break
            offset+=len(data)
        return pd.concat(pages,ignore_index=True) if pages else pd.DataFrame()
    def save(self,table,data):
        data=data.copy()
        # API dates are YYYYMMDD strings. Parse explicitly, including optional nulls.
        for col in data.columns:
            if col.endswith('_date') or col in ['trade_date']:
                data[col]=pd.to_datetime(data[col],format='%Y%m%d',errors='coerce')
        if self.codes and 'ts_code' in data and not table.startswith('index'):
            data=data[data.ts_code.isin(self.codes)]
        append_frame(self.s,TABLE_PATHS[table],table,data)
        return len(data)
    def dates(self):
        if self._dates is None:
            cal=self.query('trade_cal',exchange='SSE',start_date=self.start,end_date=self.end,is_open='1')
            self._dates=sorted(cal.cal_date.tolist())
        return self._dates
    def stock_codes(self):
        if self.codes:return self.codes
        return list(self.s.run('exec distinct ts_code from loadTable("dfs://basic_factor","stock_basic")'))
    def run(self,source):
        count=0
        if source=='stock_basic':
            for status in ['L','D','P']:
                count+=self.save(source,self.query('stock_basic',list_status=status,fields='ts_code,symbol,name,area,industry,fullname,enname,cnspell,market,exchange,curr_type,list_status,list_date,delist_date,is_hs'))
        elif source=='stock_name':
            for code in self.stock_codes():count+=self.save(source,self.query('namechange',ts_code=code))
        elif source in ['stock_daily','stock_adj_factor','stock_daily_basic','stock_limit','stock_st','stock_info','moneyflow','moneyflow_ind_ths']:
            endpoint={'stock_daily':'daily','stock_adj_factor':'adj_factor','stock_daily_basic':'daily_basic','stock_limit':'stk_limit','stock_info':'bak_basic'}.get(source,source)
            for date in self.dates():count+=self.save(source,self.query(endpoint,trade_date=date))
        elif source in ['index_basic','stock_index_basic']:
            for market in ['SSE','SZSE','CSI']:count+=self.save(source,self.query('index_basic',market=market))
        elif source=='index_daily':
            for code in INDEXES:
                # One calendar year per request plus pagination.
                for year in range(int(self.start[:4]),int(self.end[:4])+1):
                    count+=self.save(source,self.query('index_daily',ts_code=code,start_date=max(self.start,f'{year}0101'),end_date=min(self.end,f'{year}1231')))
        elif source=='index_weight':
            for code,kind in INDEXES.items():
                # Include the prior month to establish an as-of constituent universe.
                start=pd.Timestamp(self.start)-pd.DateOffset(months=1)
                for month in pd.period_range(start,pd.Timestamp(self.end),freq='M'):
                    frame=self.query('index_weight',index_code=code,start_date=month.start_time.strftime('%Y%m%d'),end_date=month.end_time.strftime('%Y%m%d'))
                    frame['index_type']=kind;count+=self.save(source,frame)
        elif source in ['quarter_stock_income','quarter_stock_balancesheet','quarter_stock_cashflow']:
            endpoint=source.removeprefix('quarter_stock_')
            # All available reporting history is needed for as-of and YoY; provider
            # schema, revisions and disclosure dates are retained in raw tables.
            fields=list(self.s.run(f'schema(loadTable("dfs://quarter_factor",{literal(source)})).colDefs.name'))
            fields=[x for x in fields if x!='update_time']
            for code in self.stock_codes():count+=self.save(source,self.query(endpoint,ts_code=code,fields=','.join(fields)))
        elif source=='stock_daily_prev':
            count=self.adjust_prices()
        else:raise ValueError(f'Unsupported source {source}; use a legacy adapter for optional datasets')
        print(f'{source}: {count} rows')
        return count
    def adjust_prices(self):
        # Stable base per ticker: first imported adjustment factor (a fixed-base
        # adjusted series). Do not rebase old rows every day using latest qfq factor.
        prices=self.s.run('select * from loadTable("dfs://day_factor","stock_daily")')
        adj=self.s.run('select ts_code,trade_date,adj_factor from loadTable("dfs://day_factor","stock_adj_factor")')
        if prices.empty or adj.empty:raise RuntimeError('Import stock_daily and stock_adj_factor first')
        if self.codes:prices=prices[prices.ts_code.isin(self.codes)]
        prices=prices.merge(adj,on=['ts_code','trade_date'],how='left').sort_values(['ts_code','trade_date'])
        if prices.adj_factor.isna().any():raise RuntimeError('Missing adjustment factors: refusing partially adjusted prices')
        anchor=prices.groupby('ts_code').adj_factor.transform('first')
        scale=prices.adj_factor/anchor
        for col in ['open','high','low','close','pre_close']:prices[col]=prices[col]*scale
        prices['change']=prices.close-prices.pre_close
        prices['pct_chg']=(prices.close/prices.pre_close-1)*100
        append_frame(self.s,'dfs://day_factor','stock_daily_prev',prices)
        return len(prices)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start',required=True,help='YYYYMMDD');p.add_argument('--end',required=True,help='YYYYMMDD')
    p.add_argument('--sources',nargs='+',default=CORE,choices=CORE+['stock_info','stock_index_basic','moneyflow','moneyflow_ind_ths'])
    p.add_argument('--codes',nargs='+');p.add_argument('--pause',type=float,default=.6)
    a=p.parse_args()
    token=os.getenv('TUSHARE_TOKEN')
    if not token:raise SystemExit('Set TUSHARE_TOKEN. For an offline installation use load_demo.py instead.')
    pd.to_datetime(a.start,format='%Y%m%d');pd.to_datetime(a.end,format='%Y%m%d')
    if a.start>a.end:raise SystemExit('start must not exceed end')
    s=connect()
    try:
        marker=s.run('exec value from loadTable("dfs://config","stockmcp_settings") where name="dataset"')
        if 'synthetic-demo' in marker:raise RuntimeError('Use a separate clean database instance for real data, not the synthetic demo')
        imp=Importer(s,token,a.start,a.end,a.codes,a.pause)
        for source in a.sources:imp.run(source)
    finally:s.close()

if __name__=='__main__':main()
