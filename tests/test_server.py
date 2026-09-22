"""Opt-in numerical regressions against an installed synthetic test instance."""
import json
import os
import uuid
import numpy as np
import pandas as pd
import pytest
from common import connect,literal

pytestmark=pytest.mark.skipif(os.getenv('STOCKMCP_TEST_SERVER')!='1',reason='requires installed synthetic instance')


def test_quintile_returns_follow_same_stock_even_when_ranks_reverse():
    s=connect();tag='regression_'+uuid.uuid4().hex[:10]
    name='rotating_'+tag
    try:
        prices=s.run('select trade_date,ts_code,close from loadTable("dfs://day_factor","stock_daily_prev")').sort_values(['ts_code','trade_date'])
        codes=sorted(prices.ts_code.unique());dates=sorted(prices.trade_date.unique())
        prices['factor_value']=prices.ts_code.map({c:i for i,c in enumerate(codes)})
        sign=prices.trade_date.map({d:(1 if i%2==0 else -1) for i,d in enumerate(dates)})
        prices['factor_value']*=sign
        prices['next_return']=prices.groupby('ts_code').close.shift(-1)/prices.close-1
        frame=prices.rename(columns={'trade_date':'tradetime','ts_code':'securityid','factor_value':'value'})[['tradetime','securityid','value']]
        s.upload({'regressionFactor':frame});s.run(f'share(regressionFactor,{literal(name)})')
        args=dict(factor=name,holdingPeriod=5.,startDate='2025.01.06',endDate='2025.03.07',industries=[],sessionId=tag)
        result=json.loads(s.run(f'callMCPTool("evaluate_stock_factor",fromStdJson({literal(json.dumps(args))}),true)'))
        actual=s.run(f'objByName({literal(result["nav_table"])})').sort_values('trade_date')
        expected=prices.dropna(subset=['next_return']).sort_values(['trade_date','factor_value','ts_code'])
        expected['layer']=expected.groupby('trade_date').cumcount()*5//expected.groupby('trade_date').ts_code.transform('count')+1
        ret=expected.groupby(['trade_date','layer']).next_return.mean().unstack()
        for layer in range(1,6):np.testing.assert_allclose(actual[f'group_{layer}'],(1+ret[layer]).cumprod(),rtol=1e-10)
    finally:
        for obj in [name,'nav_data_'+tag,'perf_metrics_'+tag]:
            try:s.run(f'try{{undef({literal(obj)},SHARED)}}catch(ex){{}}')
            except Exception:pass
        s.close()


def test_config_defaults_are_persisted_and_ids_are_unique():
    s=connect();name='cfg_'+uuid.uuid4().hex[:10]
    try:
        args=dict(backtestName=name,backtestSettings=json.dumps(dict(start_date='2025/01/06',end_date='2025/03/07',initial_capital=1000000)),tableName='unused',strategyRules='{}',positionRules='{}',rebalanceRules='{}',tradeRules='{}')
        def create():return json.loads(s.run(f'callMCPTool("create_backtest_config",fromStdJson({literal(json.dumps(args))}),true)'))
        one,two=create(),create();assert one['backtest_id']!=two['backtest_id']
        row=s.run(f'select * from loadTable("dfs://config","backtest_config") where backtest_id={literal(one["backtest_id"])}').iloc[0]
        assert json.loads(row.position_rules)['max_stocks']==10
        assert json.loads(row.strategy_rules)['factors']==['circ_mv']
        assert json.loads(row.backtest_settings)['benchmark']=='000300.SH'
    finally:s.close()


def test_reimporting_benchmark_does_not_duplicate_dates():
    from common import append_frame
    s=connect()
    try:
        rows=s.run('select * from loadTable("dfs://day_factor","index_daily")')
        assert not rows.empty
        append_frame(s,'dfs://day_factor','index_daily',rows.iloc[:1])
        after=s.run('exec count(*) from loadTable("dfs://day_factor","index_daily")')
        assert after==len(rows)
    finally:s.close()
