"""Deterministic SYNTHETIC data; refuses a non-demo installation with price data."""
import numpy as np
import pandas as pd
from common import connect, append_frame, literal
from factors import build

START='2025-01-06'
END='2025-03-07'

def load_demo(s):
    settings=s.run('select * from loadTable("dfs://config","stockmcp_settings") where name="dataset"')
    count=s.run('exec count(*) from loadTable("dfs://day_factor","stock_daily_prev")')
    if count and (settings.empty or settings.value.iloc[-1]!='synthetic-demo'):
        raise RuntimeError('Refusing to mix synthetic data with existing real prices; use an empty dedicated instance.')
    dates=pd.bdate_range(START,END)
    codes=[f'{600001+i:06d}.SH' for i in range(10)]
    basic=pd.DataFrame({'ts_code':codes,'symbol':[x[:6] for x in codes],
                        'name':[f'演示股票{i+1}' for i in range(10)],'industry':['演示行业']*10,
                        'market':['主板']*10,'list_status':['L']*10,'list_date':[pd.Timestamp('2010-01-01')]*10})
    append_frame(s,'dfs://basic_factor','stock_basic',basic)
    append_frame(s,'dfs://basic_factor','stock_name',pd.DataFrame({'ts_code':codes,'name':basic.name,
                 'start_date':pd.Timestamp('2010-01-01'),'end_date':pd.NaT,'ann_date':pd.Timestamp('2009-12-01')}))
    prices=[];daily=[];limits=[]
    for i,code in enumerate(codes):
        prev=10+i
        for j,date in enumerate(dates):
            close=prev*(1+0.0005*(i-4)+0.002*np.sin(j/3+i))
            prices.append(dict(ts_code=code,trade_date=date,open=prev,high=max(prev,close)*1.01,low=min(prev,close)*.99,
                               close=close,pre_close=prev,change=close-prev,pct_chg=(close/prev-1)*100,
                               vol=10000+100*i,amount=close*1000,adj_factor=1,turnover_rate=1+i*.1,volume_ratio=1))
            daily.append(dict(ts_code=code,trade_date=date,close=close,pe=8+i+j*.01,pe_ttm=9+i,pb=1+i*.1,
                              ps=2+i*.1,ps_ttm=2+i*.1,dv_ratio=2,dv_ttm=2,turnover_rate=1+i*.1,
                              turnover_rate_f=1+i*.1,volume_ratio=1,total_share=100000,float_share=80000,
                              free_share=60000,total_mv=close*100000,circ_mv=close*80000))
            limits.append(dict(ts_code=code,trade_date=date,pre_close=prev,up_limit=round(prev*1.1,2),down_limit=round(prev*.9,2)))
            prev=close
    for table in ['stock_daily','stock_daily_prev']:append_frame(s,'dfs://day_factor',table,pd.DataFrame(prices))
    append_frame(s,'dfs://day_factor','stock_daily_basic',pd.DataFrame(daily))
    append_frame(s,'dfs://day_factor','stock_limit',pd.DataFrame(limits))
    for kind in ['income','balancesheet','cashflow']:
        records=[]
        for i,code in enumerate(codes):
            for year in [2023,2024]:
                records.append(dict(ts_code=code,ann_date=pd.Timestamp(f'{year}-10-25'),f_ann_date=pd.Timestamp(f'{year}-10-25'),
                                    end_date=pd.Timestamp(f'{year}-09-30'),report_type='1',comp_type='1',end_type='3',
                                    revenue=1e9,n_income=(1+i*.1)*1e8,n_income_attr_p=(1+i*.1)*1e8*(1.1 if year==2024 else 1),
                                    total_assets=3e9,total_liab=1e9,total_hldr_eqy_exc_min_int=2e9,net_profit=1e8))
        append_frame(s,'dfs://quarter_factor','quarter_stock_'+kind,pd.DataFrame(records))
    for index,index_type in [('000300.SH','hs300'),('000016.SH','sz50'),('000852.SH','csi1000')]:
        append_frame(s,'dfs://basic_factor','index_basic',pd.DataFrame([dict(ts_code=index,name='演示指数_'+index_type,market='SSE',publisher='synthetic',list_date=pd.Timestamp('2010-01-01'))]))
        append_frame(s,'dfs://basic_factor','index_weight',pd.DataFrame(dict(index_code=index,con_code=codes,trade_date=dates[0],weight=10.,index_type=index_type)))
        append_frame(s,'dfs://day_factor','index_daily',pd.DataFrame(dict(ts_code=index,trade_date=dates,close=1000*np.cumprod(np.full(len(dates),1.0005)),pct_chg=.05)))
    append_frame(s,'dfs://basic_factor','stock_index_basic',pd.DataFrame([dict(ts_code='881001.TI',name='演示行业',industry='演示行业',list_date=pd.Timestamp('2010-01-01'))]))
    flow=pd.DataFrame(prices)[['ts_code','trade_date']].copy();flow['net_mf_amount']=100.
    append_frame(s,'dfs://day_factor','moneyflow',flow)
    append_frame(s,'dfs://day_factor','moneyflow_ind_ths',pd.DataFrame(dict(ts_code='881001.TI',trade_date=dates,industry='演示行业',net_buy_amount=100.)))
    # stock_info is a snapshot dataset; it is not used for point-in-time financial factors.
    info=pd.DataFrame(prices)[['ts_code','trade_date']].merge(basic[['ts_code','name','industry','list_date']],on='ts_code')
    append_frame(s,'dfs://basic_factor','stock_info',info)
    s.run('upsert!(loadTable("dfs://config","stockmcp_settings"),table(["dataset"] as name,["synthetic-demo"] as value),keyColNames=`name)')
    build(s,START,END)
    print('SYNTHETIC demo ready: 10 stocks, 45 business days; not real market data.')

if __name__=='__main__':
    session=connect()
    try:load_demo(session)
    finally:session.close()
