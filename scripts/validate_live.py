"""Real-data end-to-end acceptance; requires the documented six-stock September 2025 fixture."""
import argparse
import json
import math
import os
import uuid
from pathlib import Path
import requests
from common import connect, literal


def main():
    s=connect();tag='live_'+uuid.uuid4().hex[:12];results=[]
    def call(name,args):
        value=s.run(f'callMCPTool({literal(name)},fromStdJson({literal(json.dumps(args))}),true)')
        if isinstance(value,str):
            if value.startswith('错误') or value.startswith('以下因子'):raise AssertionError(value)
            try:value=json.loads(value)
            except json.JSONDecodeError:pass
        assert '查询成功' not in str(value) or '[]' not in str(value), f'{name}: empty result'
        results.append({'tool':name,'ok':True})
        print('PASS',name,flush=True)
        return value
    try:
        assert s.run('getDBname("stock_daily")')=='day_factor'
        info=call('get_date_info',{});assert info['latest_trade_date']=='2025.09.12'
        meta=call('search_stock_factor_meta_by_keywords',{'keywords':'市盈率'})
        assert 'pe' in [x['factor_name'] for x in meta['factormetas']]
        extra_calls=[
            ('get_stock_code_by_name',dict(StockName='贵州茅台',resultTableName='',sessionId='')),
            ('get_stock_basic_info',dict(stockCodes=['600519.SH'],resultTableName='',sessionId='')),
            ('get_stock_info',dict(stockCodes=['600519.SH'],dates=['2025.09.01'],resultTableName='',sessionId='')),
            ('get_stock_daily_prev',dict(stockCodes=['600519.SH'],dates=['2025.09.01'],resultTableName='',sessionId='')),
            ('get_stock_moneyflow',dict(stockCodes=['600519.SH'],startDate='2025.09.01',endDate='2025.09.12',is_aggregate=True,resultTableName='',sessionId='')),
            ('get_industry_code_by_name',dict(KeywordList=['沪深300'],resultTableName='',sessionId='')),
            ('get_industry_info',dict(indexCodes=['000300.SH'])),
            ('get_industry_moneyflow',dict(industryCodes=[],dates=['2025.09.01'],rowNum=10.,resultTableName='',sessionId='')),
            ('search_industry_factor_meta_by_keywords',dict(keywords='流入')),
            ('select_industries_by_factors',dict(selectCols=['ts_code','industry','trade_date','net_buy_amount'],whereCondition='trade_date >= 2025.09.01',orderbyCols=['net_buy_amount'],ascOrder=[0.],resultsName='')),
        ]
        for statement in ['income','balancesheet','cashflow']:
            extra_calls.append(('get_financial_statements_'+statement,dict(stockCodes=['600519.SH'],dates=['2025.06.30'],resultTableName='',sessionId='')))
        for name,args in extra_calls:
            if name=='get_financial_statements_balancesheet':args['endDates']=args.pop('dates')
            call(name,args)
        selected=call('select_stocks_by_conditions',{'strDates':json.dumps({'startDate':'2025-09-01','endDate':'2025-09-12'}),
                      'strRules':json.dumps({'base_index':'hs300','industry':'','filter_expr':'pe > 0','factors':['pe']}),
                      'resultsName':tag})
        assert selected['股票数量']==6
        assessment=call('evaluate_stock_factor',{'factor':'pe','holdingPeriod':5.,'startDate':'2025.09.01','endDate':'2025.09.12','industries':[], 'sessionId':tag})
        assert math.isfinite(assessment['mean_ic'])
        config=call('create_backtest_config',{'backtestName':'Real-data deployment acceptance',
                    'backtestSettings':json.dumps({'start_date':'2025-09-01','end_date':'2025-09-12','initial_capital':1000000,'benchmark':'000300.SH'}),
                    'tableName':tag,'strategyRules':json.dumps({'factors':['pe'],'weights':[1]}),
                    'positionRules':json.dumps({'max_stocks':5,'weight_method':'equal'}),
                    'rebalanceRules':json.dumps({'weekday':'Tuesday','holding_period':5}),
                    'tradeRules':json.dumps({'commission_rate':.0015})})
        report=call('run_backtest',{'backtestId':config['backtest_id']})
        assert math.isfinite(report['nav']) and report['nav']>0
        path=call('export_table_to_csv',{'tableName':tag})
        assert isinstance(path,str) and '.csv' in path
        call('clean_memory',{'sessionid':tag})
        # Protocol-level auth + initialization + discovery + call, with a fresh ticket.
        token=s.run('getAuthenticatedUserTicket()')
        url=f'http://{os.getenv("DDB_HOST","127.0.0.1")}:{os.getenv("DDB_PORT","8848")}/mcp'
        http=requests.Session();http.trust_env=False
        headers={'Authorization':'Bearer '+token,'Accept':'application/json, text/event-stream','Content-Type':'application/json'}
        def rpc(method,params,ident):
            response=http.post(url,headers=headers,json={'jsonrpc':'2.0','id':ident,'method':method,'params':params},timeout=30)
            response.raise_for_status()
            if 'Mcp-Session-Id' in response.headers:headers['Mcp-Session-Id']=response.headers['Mcp-Session-Id']
            if response.headers.get('Content-Type','').startswith('text/event-stream'):
                payloads=[json.loads(x[5:].strip()) for x in response.text.splitlines() if x.startswith('data:')]
                value=next(x for x in payloads if x.get('id')==ident)
            else:value=response.json()
            assert 'error' not in value,value
            return value['result']
        rpc('initialize',{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'StockMCP smoke','version':'1.0'}},1)
        http.post(url,headers=headers,json={'jsonrpc':'2.0','method':'notifications/initialized'},timeout=10).raise_for_status()
        discovered=rpc('tools/list',{},2)
        assert len(discovered['tools'])>=21
        response=rpc('tools/call',{'name':'get_date_info','arguments':{}},3)
        assert not response.get('isError',False),response
        results.append({'transport':'Streamable HTTP','tool_count':len(discovered['tools']),'ok':True})
        out=Path('artifacts');out.mkdir(exist_ok=True)
        (out/'live_smoke.json').write_text(json.dumps({'results':results,'backtest':report,'factor':assessment},ensure_ascii=False,indent=2,default=str))
        print('PASS HTTP MCP initialize, tools/list, tools/call; real-data workflow complete.')
    finally:
        # Clear only objects created by this test, not other users' shared tables.
        for name in [tag,'nav_data_'+tag,'perf_metrics_'+tag]:
            try:s.run(f'try {{undef({literal(name)},SHARED)}} catch(ex){{}}')
            except Exception:pass
        s.close()

if __name__=='__main__':main()
