#!/usr/bin/env python
# coding: utf-8
import basic
import tushare as ts
import pandas as pd
from datetime import datetime
import time
import dolphindb as ddb
import logging
import warnings
warnings.filterwarnings("ignore")

# 设置日志配置
logger_stock_monthly_back = logging.getLogger('logger_stock_monthly_back')
logger_stock_monthly_back.setLevel(logging.INFO)
# 日志输出到文件
fileHandler_stock_monthly_back = logging.FileHandler(basic.logDir + "/stock_monthly_back.log")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fileHandler_stock_monthly_back.setFormatter(formatter)
# 日志输出到控制台
console_stock_monthly_back = logging.StreamHandler() 
console_stock_monthly_back.setFormatter(formatter)
# 将 Handler 添加到 Logger
logger_stock_monthly_back.addHandler(fileHandler_stock_monthly_back)
logger_stock_monthly_back.addHandler(console_stock_monthly_back)

def get_data(ts_code, appender, startDate, endDate, token, dataSource, s, maxRetries):
    ts.set_token(token)
    retry_count = 0  # 初始化重试计数器
    max_retries = maxRetries  # 最大重试次数
    while retry_count < max_retries:
        try:
            data = ts.pro_bar(ts_code=ts_code, freq='M', adj='hfq', start_date=startDate, end_date=endDate, ma=[5, 20, 50], factors=['tor', 'vr'], adjfactor=True)
            if data is not None and len(data) != 0:
                data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d')
                data = data[["ts_code","trade_date","open","high","low","close","pre_close","change","pct_chg","vol","amount", "adj_factor", "ma5", "ma_v_5", "ma20", "ma_v_20", "ma50", "ma_v_50"]]
                data['update_time'] = datetime.now()
                appender.append(data)
                logger_stock_monthly_back.info("Data of %s %s has been written.", dataSource, ts_code)
                return
            else:
                s.run('writeLogLevel(WARNING, "'+'easyTushareImport - '+dataSource+' - '+dataSource+' '+ts_code+' has no data.")')
                logger_stock_monthly_back.warning("%s %s has no data.", dataSource, ts_code)
                return
        except Exception as e:
            retry_count += 1
            s.run('writeLogLevel(WARNING, "'+'easyTushareImport - '+dataSource+' - Failed to get data of '+dataSource+' '+ts_code+'. Will retry in 10 seconds. Error: '+str(e).replace('"',"'")+'")')
            logger_stock_monthly_back.warning("Failed to get data of %s %s. Will retry in 10 seconds. Error: %s", dataSource, ts_code, e)
            time.sleep(10)
    # 如果达到最大重试次数，记录错误并抛出异常
    logger_stock_monthly_back.error("Failed to get data of %s after %d attempts. Exiting.", dataSource, max_retries)
    raise Exception(f"Failed to get data of {dataSource} after {max_retries} attempts. Exiting.")

def main(session, startDate, endDate, token, dataSource, maxRetries):
    # 与 DolphinDB 建立会话和连接
    s = ddb.session(session["host"], session["port"], session["username"], session["password"])
    # 初始化库表：沪深股票 - 行情数据 - 月线复权行情（后复权）
    scripts = """
    use DolphinDBModules::EasyTushare::createDBTB
    createStockMonthlyBack()
    """
    #s.run(scripts)
    dbname = s.run("getDBname('{}')".format(dataSource))  
    # 初始化python写入接口
    appender = ddb.TableAppender(dbPath='dfs://'+dbname, tableName=dataSource, ddbSession=s)
    pro = ts.pro_api(token)

    ts_codes = pro.stock_basic(list_status='L', fields=['ts_code'])

    for ts_code in ts_codes['ts_code'].values:
        get_data(ts_code, appender, startDate, endDate, token, dataSource, s, maxRetries)

    logger_stock_monthly_back.info("The %s data import is complete.", dataSource)
