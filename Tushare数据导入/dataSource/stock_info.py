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
logger_stock_info = logging.getLogger('logger_stock_info')
logger_stock_info.setLevel(logging.INFO)
# 日志输出到文件
fileHandler_stock_info = logging.FileHandler(basic.logDir + "/stock_info.log")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fileHandler_stock_info.setFormatter(formatter)
# 日志输出到控制台
console_stock_info = logging.StreamHandler() 
console_stock_info.setFormatter(formatter)
# 将 Handler 添加到 Logger
logger_stock_info.addHandler(fileHandler_stock_info)
logger_stock_info.addHandler(console_stock_info)

def get_data(trade_date, appender, token, dataSource, s, maxRetries):
    pro = ts.pro_api(token)
    retry_count = 0  # 初始化重试计数器
    max_retries = 1  # 最大重试次数
    while retry_count < max_retries:
        try:
            data = pro.bak_basic(trade_date=trade_date, list_status='L', fields=["ts_code", "trade_date", "name", "industry", "area", "pe", "float_share", "total_share", "total_assets", "liquid_assets", "fixed_assets", "reserved", "reserved_pershare", "eps", "bvps", "pb", "list_date", "undp", "per_undp", "rev_yoy", "profit_yoy", "gpr", "npr", "holder_num"])
            data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d')
            # 剔除无意义数据：list_date 列为 0
            zero_list_date_rows = data[data["list_date"] == "0"]
            # 输出日志
            if not zero_list_date_rows.empty:
                logger_stock_info.warning(f"Found {len(zero_list_date_rows)} rows with list_date = 0. These rows will be removed.")
                # 剔除 list_date 为 0 的行
                data = data[data["list_date"] != "0"]
            data['list_date'] = pd.to_datetime(data['list_date'], format='%Y%m%d')
            data['update_time'] = datetime.now()
            appender.append(data)
            logger_stock_info.info("Data of %s for %s has been written.", dataSource, trade_date)
            return
        except Exception as e:
            retry_count += 1
            s.run('writeLogLevel(WARNING, "'+'easyTushareImport - '+dataSource+' - Failed to get data of '+dataSource+' '+trade_date+'. Will retry in 10 seconds. Error: '+str(e).replace('"',"'")+'")')
            logger_stock_info.warning("Failed to get data of %s %s. Will retry in 10 seconds. Error: %s", dataSource, trade_date, e)
            time.sleep(10)
    # 如果达到最大重试次数，记录错误并抛出异常
    logger_stock_info.error("Failed to get data of %s after %d attempts. Exiting.", dataSource, max_retries)
    raise Exception(f"Failed to get data of {dataSource} after {max_retries} attempts. Exiting.")

def main(session, startDate, endDate, token, dataSource, maxRetries):
    # 与 DolphinDB 建立会话和连接
    s = ddb.session(session["host"], session["port"], session["username"], session["password"])
    # 初始化库表：沪深股票 - 基础数据 - 备用列表
    scripts = """
    use DolphinDBModules::EasyTushare::createDBTB
    createStockInfo()
    """
    #s.run(scripts)
    dbname = s.run("getDBname('{}')".format(dataSource))  
    # 初始化python写入接口
    appender = ddb.TableAppender(dbPath='dfs://'+dbname, tableName=dataSource, ddbSession=s)
    pro = ts.pro_api(token)

    trade_dates = pro.trade_cal(exchange='SSE', is_open='1', start_date=startDate, end_date=endDate, fields='cal_date')

    for trade_date in trade_dates['cal_date'].values:
        get_data(trade_date, appender, token, dataSource, s, maxRetries)

    logger_stock_info.info("The %s data import is complete.", dataSource)