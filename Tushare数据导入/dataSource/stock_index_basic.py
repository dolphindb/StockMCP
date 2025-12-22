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
logging_stock_index_basic = logging.getLogger('logging_stock_index_basic')
logging_stock_index_basic.setLevel(logging.INFO)
# 日志输出到文件
fileHandler_stock_index_basic = logging.FileHandler(basic.logDir + "/stock_index_basic.log")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fileHandler_stock_index_basic.setFormatter(formatter)
# 日志输出到控制台
console_stock_index_basic = logging.StreamHandler() 
console_stock_index_basic.setFormatter(formatter)
# 将 Handler 添加到 Logger
logging_stock_index_basic.addHandler(fileHandler_stock_index_basic)
logging_stock_index_basic.addHandler(console_stock_index_basic)

def main(session, startDate, endDate, token, dataSource, maxRetries):
    # 与 DolphinDB 建立会话和连接
    s = ddb.session(session["host"], session["port"], session["username"], session["password"])
    # 初始化库表：沪深股票 - 基础数据 - 股票列表
    scripts = """
    use DolphinDBModules::easyTushare::createDBTB
    createStockIndexBasic()
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
            data = pro.index_basic(list_status='L', fields=["ts_code", "name", "fullname", "market", "publisher", "index_type", "category", "base_date", "base_point", "list_date", "weight_rule", "desc", "exp_date"])
            data = data[["ts_code", "name", "fullname", "market", "publisher", "index_type", "category", "base_date", "base_point", "list_date", "weight_rule", "desc", "exp_date"]]
            data['list_date'] = pd.to_datetime(data['list_date'], format='%Y%m%d')
            data['base_date'] = pd.to_datetime(data['base_date'], format='%Y%m%d')
            data['exp_date'] = pd.to_datetime(data['exp_date'], format='%Y%m%d')
            data['update_time'] = datetime.now()
            appender.append(data)
            logging_stock_index_basic.info("The %s data import is complete.", dataSource)
            return
        except Exception as e:
            retry_count += 1
            s.run('writeLogLevel(ERROR, "'+'easyTushareImport - '+dataSource+' - Failed to get data of '+dataSource+'. Will retry in 10 seconds. Error: '+str(e).replace('"',"'")+'")')
            logging_stock_index_basic.error("Failed to get data of %s. Will retry in 10 seconds. Error: %s", dataSource, e)
            time.sleep(10)
    # 如果达到最大重试次数，记录错误并抛出异常
    logging_stock_index_basic.error("Failed to get data of %s after %d attempts. Exiting.", dataSource, max_retries)
    raise Exception(f"Failed to get data of {dataSource} after {max_retries} attempts. Exiting.")
