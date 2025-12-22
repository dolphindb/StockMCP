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
logger_stock_name = logging.getLogger('logger_stock_name')
logger_stock_name.setLevel(logging.INFO)
# 日志输出到文件
fileHandler_stock_name = logging.FileHandler(basic.logDir + "/stock_name.log")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fileHandler_stock_name.setFormatter(formatter)
# 日志输出到控制台
console_stock_name = logging.StreamHandler() 
console_stock_name.setFormatter(formatter)
# 将 Handler 添加到 Logger
logger_stock_name.addHandler(fileHandler_stock_name)
logger_stock_name.addHandler(console_stock_name)

def main(session, startDate, endDate, token, dataSource, maxRetries):
    # 与 DolphinDB 建立会话和连接
    s = ddb.session(session["host"], session["port"], session["username"], session["password"])
    # 初始化库表：沪深股票 - 基础数据 - 股票曾用名
    scripts = """
    use DolphinDBModules::EasyTushare::createDBTB
    createStockName()
    """
    #s.run(scripts)
    dbname = s.run("getDBname('{}')".format(dataSource))  
    # 初始化python写入接口
    appender = ddb.TableAppender(dbPath='dfs://'+dbname, tableName=dataSource, ddbSession=s)
    pro = ts.pro_api(token)

    retry_count = 0  # 初始化重试计数器
    max_retries = maxRetries  # 最大重试次数
    while retry_count < max_retries:
        try:
            data = pro.namechange(start_date='19900101', end_date='')
            data = data[["ts_code", "name", "start_date", "end_date", "ann_date", "change_reason"]]
            data['start_date'] = pd.to_datetime(data['start_date'], format='%Y%m%d')
            data['end_date'] = pd.to_datetime(data['end_date'], format='%Y%m%d')
            data['ann_date'] = pd.to_datetime(data['ann_date'], format='%Y%m%d')
            data['update_time'] = datetime.now()
            appender.append(data)
            logger_stock_name.info("The %s data import is complete.", dataSource)
            return
        except Exception as e:
            retry_count += 1
            s.run('writeLogLevel(WARNING, "'+'easyTushareImport - '+dataSource+' - Failed to get data of '+dataSource+'. Will retry in 10 seconds. Error: '+str(e).replace('"',"'")+'")')
            logger_stock_name.warning("Failed to get data of %s. Will retry in 10 seconds. Error: %s", dataSource, e)
            time.sleep(10)
    # 如果达到最大重试次数，记录错误并抛出异常
    logger_stock_name.error("Failed to get data of %s after %d attempts. Exiting.", dataSource, max_retries)
    raise Exception(f"Failed to get data of {dataSource} after {max_retries} attempts. Exiting.")