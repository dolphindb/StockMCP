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
logger_stock_new = logging.getLogger('logger_stock_new')
logger_stock_new.setLevel(logging.INFO)
# 日志输出到文件
fileHandler_stock_new = logging.FileHandler(basic.logDir + "/stock_new.log")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fileHandler_stock_new.setFormatter(formatter)
# 日志输出到控制台
console_stock_new = logging.StreamHandler() 
console_stock_new.setFormatter(formatter)
# 将 Handler 添加到 Logger
logger_stock_new.addHandler(fileHandler_stock_new)
logger_stock_new.addHandler(console_stock_new)

def get_data(trade_date, appender, token, dataSource, s, maxRetries):
    pro = ts.pro_api(token)
    retry_count = 0  # 初始化重试计数器
    max_retries = maxRetries  # 最大重试次数
    while retry_count < max_retries:
        try:
            data = pro.new_share(start_date=trade_date, end_date=trade_date, list_status='L')
            data = data[["ts_code", "name", "ipo_date", "issue_date", "amount", "market_amount", "price", "pe", "limit_amount", "funds", "ballot"]]
            data['ipo_date'] = pd.to_datetime(data['ipo_date'], format='%Y%m%d')
            data['issue_date'] = pd.to_datetime(data['issue_date'], format='%Y%m%d')
            data['update_time'] = datetime.now()
            appender.append(data)
            logger_stock_new.info("Data of %s for %s has been written.", dataSource, trade_date)
            return
        except Exception as e:
            retry_count += 1
            s.run('writeLogLevel(WARNING, "'+'easyTushareImport - '+dataSource+' - Failed to get data of '+dataSource+' '+trade_date+'. Will retry in 10 seconds. Error: '+str(e).replace('"',"'")+'")')
            logger_stock_new.warning("Failed to get data of %s %s. Will retry in 10 seconds. Error: %s", dataSource, trade_date, e)
            time.sleep(10)
    # 如果达到最大重试次数，记录错误并抛出异常
    logger_stock_new.error("Failed to get data of %s after %d attempts. Exiting.", dataSource, max_retries)
    raise Exception(f"Failed to get data of {dataSource} after {max_retries} attempts. Exiting.")

def main(session, startDate, endDate, token, dataSource, maxRetries):
    # 与 DolphinDB 建立会话和连接
    s = ddb.session(session["host"], session["port"], session["username"], session["password"])
    # 初始化库表：沪深股票 - 基础数据 - IPO 新股列表
    scripts = """
    use DolphinDBModules::EasyTushare::createDBTB
    createStockNew()
    """
    #s.run(scripts)
    dbname = s.run("getDBname('{}')".format(dataSource))  
    # 初始化python写入接口
    appender = ddb.TableAppender(dbPath='dfs://'+dbname, tableName=dataSource, ddbSession=s)
    pro = ts.pro_api(token)

    trade_dates = pro.trade_cal(exchange='SSE', is_open='1', start_date=startDate, end_date=endDate, fields='cal_date')

    for trade_date in trade_dates['cal_date'].values:
        get_data(trade_date, appender, token, dataSource, s, maxRetries)

    logger_stock_new.info("The %s data import is complete.", dataSource)