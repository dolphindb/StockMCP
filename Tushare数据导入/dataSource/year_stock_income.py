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
logger_stock_income = logging.getLogger('logger_stock_income')
logger_stock_income.setLevel(logging.INFO)
# 日志输出到文件
fileHandler_stock_income = logging.FileHandler(basic.logDir + "/stock_income.log")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fileHandler_stock_income.setFormatter(formatter)
# 日志输出到控制台
console_stock_income = logging.StreamHandler() 
console_stock_income.setFormatter(formatter)
# 将 Handler 添加到 Logger
logger_stock_income.addHandler(fileHandler_stock_income)
logger_stock_income.addHandler(console_stock_income)

def get_data(ts_code, appender, token, dataSource, s, maxRetries):
    #ts.set_token(token)
    pro = ts.pro_api(token)
    retry_count = 0  # 初始化重试计数器
    max_retries = maxRetries  # 最大重试次数
    while retry_count < max_retries:
        try:
            data = pro.income(ts_code=ts_code)
            if data is not None:
                #data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d')
                data['end_date'] = pd.to_datetime(data['end_date'], format='%Y%m%d')
                #print(data['end_date'])
                data['ann_date'] = pd.to_datetime(data['ann_date'], format='%Y%m%d')
                data['f_ann_date'] = pd.to_datetime(data['f_ann_date'], format='%Y%m%d')
                data['end_date'] = pd.to_datetime(data['end_date'], format='%Y%m%d')
                data['update_time'] = datetime.now()
                #print(data.columns)
                #print(len(data.columns))
                dataYearEnd = data[data['end_date'].dt.is_year_end]
                #print(dataYearEnd)
                appender.append(dataYearEnd)
                logger_stock_income.info("Data of %s %s has been written.", dataSource, ts_code)
                return
            else:
                s.run('writeLogLevel(WARNING, "'+'easyTushareImport - '+dataSource+' - '+dataSource+' '+ts_code+' has no data.")')
                logger_stock_income.warning("%s %s has no data.", dataSource, ts_code)
                return
        except Exception as e:
            retry_count += 1
            s.run('writeLogLevel(WARNING, "'+'easyTushareImport - '+dataSource+' - Failed to get data of '+dataSource+' '+ts_code+'. Will retry in 10 seconds. Error: '+str(e).replace('"',"'")+'")')
            logger_stock_income.warning("Failed to get data of %s %s. Will retry in 10 seconds. Error: %s", dataSource, ts_code, e)
            time.sleep(10)
    # 如果达到最大重试次数，记录错误并抛出异常
    logger_stock_income.error("Failed to get data of %s after %d attempts. Exiting.", dataSource, max_retries)
    raise Exception(f"Failed to get data of {dataSource} after {max_retries} attempts. Exiting.")

def main(session, startDate, endDate, token, dataSource, maxRetries):
    # 与 DolphinDB 建立会话和连接
    s = ddb.session(session["host"], session["port"], session["username"], session["password"])
    # 初始化库表
    scripts = """
    use DolphinDBModules::easyTushare::createDBTB
    createStockIncome()
    """
    # s.run(scripts)
    dbname = s.run("getDBname('{}')".format(dataSource)) 
    # 初始化python写入接口
    appender = ddb.TableAppender(dbPath='dfs://'+dbname, tableName=dataSource, ddbSession=s)

    pro = ts.pro_api(token)
    # 获取导入股票代码
    ts_codes = pro.stock_basic(list_status='L', fields=['ts_code'])
    for ts_code in ts_codes['ts_code'].values:
        get_data(ts_code, appender, token, dataSource, s, maxRetries)
    # python log 日志
    logger_stock_income.info("The %s data import is complete.", dataSource)
