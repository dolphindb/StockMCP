"""Build dated factor observations from published raw table schemas.

Financial reports become usable strictly AFTER max(ann_date, f_ann_date).
No backward fill from a future report. Ratios use YTD statements, not TTM.
"""
import argparse
import numpy as np
import pandas as pd
from common import connect, append_frame, literal

PRICE = {'open':'固定基准复权开盘价','high':'固定基准复权最高价','low':'固定基准复权最低价','close':'固定基准复权收盘价',
         'vol':'成交量，手','amount':'成交金额，千元','pct_chg':'当日涨跌幅，百分数'}
DAILY = {'pe':'市盈率 PE','pe_ttm':'滚动市盈率 TTM PE','pb':'市净率 PB','ps':'市销率',
         'ps_ttm':'滚动市销率','dv_ratio':'股息率，百分数','dv_ttm':'滚动股息率，百分数',
         'turnover_rate':'换手率，百分数','turnover_rate_f':'自由流通换手率，百分数',
         'volume_ratio':'量比','total_share':'总股本，万股','float_share':'流通股本，万股',
         'free_share':'自由流通股本，万股','total_mv':'总市值，万元','circ_mv':'流通市值，万元'}
DERIVED = {
    'ROE':('净资产收益率，累计归母净利润/期末归母权益，比例；非年化、非平均权益口径','盈利能力 净资产回报率 return on equity'),
    'net_profit_margin':('净利率，累计净利润/累计营业收入，比例；不是净利润增长率','盈利能力 销售净利率 profit margin'),
    'debt_ratio':('资产负债率，总负债/总资产，比例','杠杆 负债 资产债务 debt assets'),
    'profit_yoy':('同报告期累计归母净利润同比，比例；上年同期非正时为空','净利润增长率 净利增速 growth'),
    'list_days':('自上市日起的自然日数，非交易日数','上市天数 次新股'),
    'ST':('历史名称是否包含 ST，1=是；无历史名称覆盖时为空','特别处理 风险警示'),
    'S':('当日原始行情成交量为0时为1，否则为0；无原始行情时为空','停牌 暂停交易'),
    'is_up_limit':('原始收盘价达到当日涨停价，1=是；无涨跌停价时为空','涨停'),
    'is_down_limit':('原始收盘价达到当日跌停价，1=是；无涨跌停价时为空','跌停'),
    'main_board':('代码以60或00开头的主板股票，1=是','主板'),
    'chi_next_board':('代码以30开头的创业板股票，1=是','创业板'),
    'star_market_board':('代码以68开头的科创板股票，1=是','科创板'),
}

def metadata_frame():
    rows=[]
    for name, desc in {**PRICE, **DAILY}.items():
        source='stock_daily_prev' if name in PRICE else 'stock_daily_basic'
        rows.append(dict(factor_name=name, database_name='dfs://factor/', table_name='day_factor',
                         description=desc, factor_code=name, source_table='dfs://factor/day_factor',
                         retrieval_text=name+' '+desc))
    for name,(desc,alias) in DERIVED.items():
        rows.append(dict(factor_name=name,database_name='dfs://factor/',table_name='day_factor',
                         description=desc,factor_code=name,source_table='dfs://factor/day_factor',
                         retrieval_text=name+' '+desc+' '+alias))
    return pd.DataFrame(rows)

def read(session, database, table, start=None, end=None, datecol='trade_date'):
    q=f'select * from loadTable({literal(database)},{literal(table)})'
    if start is not None:
        q+=f' where {datecol} >= date({literal(str(start))}) and {datecol} <= date({literal(str(end))})'
    return session.run(q)

def financial_observations(frame, kind):
    if frame.empty: return pd.DataFrame()
    df=frame.copy()
    for key in ('ann_date','f_ann_date','end_date'):
        df[key]=pd.to_datetime(df[key], errors='coerce')
    df['available_date']=df[['ann_date','f_ann_date']].max(axis=1)
    df=df.dropna(subset=['ts_code','available_date','end_date'])
    # Consolidated original/amended statements only; exclude parent-only statements.
    if 'report_type' in df:
        df=df[df.report_type.astype(str).isin(['1','4','5'])]
    # A later correction of an OLD quarter must not replace a more recent report.
    df=df.sort_values(['ts_code','available_date','end_date'])
    df=df.drop_duplicates(['ts_code','available_date','end_date'],keep='last')
    outputs=[]
    for code, group in df.groupby('ts_code',sort=False):
        history={}
        for available, updates in group.groupby('available_date',sort=True):
            for row in updates.to_dict('records'): history[row['end_date']]=row
            latest=max(history); row=history[latest]
            out={'ts_code':code,'available_date':available}
            if kind=='income':
                revenue=row.get('revenue',np.nan); profit=row.get('n_income',np.nan)
                parent=row.get('n_income_attr_p',np.nan)
                prev=history.get(latest-pd.DateOffset(years=1),{})
                prev_profit=prev.get('n_income_attr_p',np.nan)
                out.update(net_profit_margin=profit/revenue if revenue>0 else np.nan,
                           profit_yoy=parent/prev_profit-1 if prev_profit>0 else np.nan,
                           parent_profit=parent,income_end_date=latest)
            else:
                assets=row.get('total_assets',np.nan); debt=row.get('total_liab',np.nan)
                out.update(debt_ratio=debt/assets if assets>0 else np.nan,
                           equity=row.get('total_hldr_eqy_exc_min_int',np.nan),balance_end_date=latest)
            outputs.append(out)
    return pd.DataFrame(outputs)

def attach_asof(base, observations):
    if observations.empty: return base
    # allow_exact_matches=False conservatively makes announcement-day values unavailable.
    return pd.merge_asof(base.sort_values('trade_date'),observations.sort_values('available_date'),
                         left_on='trade_date',right_on='available_date',by='ts_code',
                         allow_exact_matches=False,direction='backward').drop(columns='available_date')

def build_frame(raw):
    prices=raw['stock_daily_prev'].copy()
    if prices.empty: raise ValueError('stock_daily_prev is empty: import prices or load the demo first')
    prices['trade_date']=pd.to_datetime(prices.trade_date)
    base=prices[['ts_code','trade_date']+list(PRICE)].drop_duplicates(['ts_code','trade_date'],keep='last')
    daily=raw['stock_daily_basic']
    if not daily.empty:
        base=base.merge(daily[['ts_code','trade_date']+list(DAILY)].drop_duplicates(['ts_code','trade_date'],keep='last'),on=['ts_code','trade_date'],how='left')
    basic=raw['stock_basic']
    base=base.merge(basic[['ts_code','list_date']].drop_duplicates('ts_code',keep='last'),on='ts_code',how='left')
    base['list_days']=(base.trade_date-pd.to_datetime(base.list_date)).dt.days
    for name,prefix in [('main_board',('60','00')),('chi_next_board',('30',)),('star_market_board',('68',))]:
        base[name]=base.ts_code.str.startswith(prefix).astype(float)
    unadjusted=raw['stock_daily'][['ts_code','trade_date','close','vol']].rename(columns={'close':'raw_close','vol':'raw_vol'})
    base=base.merge(unadjusted.drop_duplicates(['ts_code','trade_date'],keep='last'),on=['ts_code','trade_date'],how='left')
    base['S']=np.where(base.raw_vol.notna(),(base.raw_vol==0).astype(float),np.nan)
    limits=raw['stock_limit'][['ts_code','trade_date','up_limit','down_limit']]
    base=base.merge(limits.drop_duplicates(['ts_code','trade_date'],keep='last'),on=['ts_code','trade_date'],how='left')
    for name,limit,up in [('is_up_limit','up_limit',True),('is_down_limit','down_limit',False)]:
        valid=base.raw_close.notna() & base[limit].notna()
        hit=base.raw_close>=base[limit]-1e-8 if up else base.raw_close<=base[limit]+1e-8
        base[name]=np.where(valid,hit.astype(float),np.nan)
    base['ST']=np.nan
    names=raw['stock_name']
    for row in names.itertuples():
        mask=(base.ts_code==row.ts_code)&(base.trade_date>=pd.Timestamp(row.start_date))
        if pd.notna(row.end_date):mask &= base.trade_date<=pd.Timestamp(row.end_date)
        base.loc[mask,'ST']=float('ST' in str(row.name).upper())
    base=attach_asof(base,financial_observations(raw['quarter_stock_income'],'income'))
    base=attach_asof(base,financial_observations(raw['quarter_stock_balancesheet'],'balance'))
    if {'parent_profit','equity','income_end_date','balance_end_date'} <= set(base):
        valid=(base.equity>0)&(base.income_end_date==base.balance_end_date)
        base['ROE']=np.where(valid,base.parent_profit/base.equity,np.nan)
    columns=[x for x in list(PRICE)+list(DAILY)+list(DERIVED) if x in base]
    frame=base.melt(id_vars=['ts_code','trade_date'],value_vars=columns,var_name='factorname',value_name='value')
    frame=frame.rename(columns={'ts_code':'securityid','trade_date':'tradetime'})
    frame['value']=pd.to_numeric(frame.value,errors='coerce')
    return frame.replace([np.inf,-np.inf],np.nan)[['tradetime','securityid','value','factorname']]

def build(session,start,end):
    raw={}
    for table in ['stock_daily_prev','stock_daily_basic','stock_daily','stock_limit']:
        raw[table]=read(session,'dfs://day_factor',table,start,end)
    for table in ['stock_basic','stock_name']:raw[table]=read(session,'dfs://basic_factor',table)
    for table in ['quarter_stock_income','quarter_stock_balancesheet']:
        raw[table]=read(session,'dfs://quarter_factor',table)
    frame=build_frame(raw)
    append_frame(session,'dfs://factor','day_factor',frame)
    print(f'Built {len(frame)} factor observations ({start} to {end}); nulls preserve missing inputs.')
    return frame

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--start',required=True);parser.add_argument('--end',required=True)
    args=parser.parse_args()
    s=connect()
    try:build(s,args.start,args.end)
    finally:s.close()
