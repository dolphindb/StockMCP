'''
Author: tanhua hua.tan@dolphindb.com
Date: 2025-10-21 16:22:33
LastEditors: tanhua hua.tan@dolphindb.com
LastEditTime: 2025-10-22 12:02:07
FilePath: \PythonModules\TushareToDDB\dataSource\stock_daily_prev.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''
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
logger_stock_daily_prev = logging.getLogger('logger_stock_daily_prev')
logger_stock_daily_prev.setLevel(logging.INFO)
# 日志输出到文件
fileHandler_stock_daily_prev = logging.FileHandler(basic.logDir + "/stock_daily_prev.log")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fileHandler_stock_daily_prev.setFormatter(formatter)
# 日志输出到控制台
console_stock_daily_prev = logging.StreamHandler() 
console_stock_daily_prev.setFormatter(formatter)
# 将 Handler 添加到 Logger
logger_stock_daily_prev.addHandler(fileHandler_stock_daily_prev)
logger_stock_daily_prev.addHandler(console_stock_daily_prev)

def get_data(ts_code, appender, startDate, endDate, token, dataSource, s, maxRetries):
    ts.set_token(token)
    retry_count = 0  # 初始化重试计数器
    max_retries = maxRetries  # 最大重试次数
    while retry_count < max_retries:
        try:
            data = ts.pro_bar(ts_code=ts_code, adj='qfq', start_date=startDate, end_date=endDate, ma=[5, 20, 50], factors=['tor', 'vr'], adjfactor=True)
            if data is not None and len(data) != 0:
                data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d')
                data = data[["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount", "turnover_rate", "volume_ratio", "adj_factor", "ma5", "ma_v_5", "ma20", "ma_v_20", "ma50", "ma_v_50"]]
                data['update_time'] = datetime.now()
                appender.append(data)
                logger_stock_daily_prev.info("Data of %s %s has been written.", dataSource, ts_code)
                return
            else:
                s.run('writeLogLevel(WARNING, "'+'easyTushareImport - '+dataSource+' - '+dataSource+' '+ts_code+' has no data.")')
                logger_stock_daily_prev.warning("%s %s has no data.", dataSource, ts_code)
                return
        except Exception as e:
            retry_count += 1
            s.run('writeLogLevel(WARNING, "'+'easyTushareImport - '+dataSource+' - Failed to get data of '+dataSource+' '+ts_code+'. Will retry in 10 seconds. Error: '+str(e).replace('"',"'")+'")')
            logger_stock_daily_prev.warning("Failed to get data of %s %s. Will retry in 10 seconds. Error: %s", dataSource, ts_code, e)
            time.sleep(10)
    # 如果达到最大重试次数，记录错误并抛出异常
    logger_stock_daily_prev.error("Failed to get data of %s after %d attempts. Exiting.", dataSource, max_retries)
    raise Exception(f"Failed to get data of {dataSource} after {max_retries} attempts. Exiting.")

def main(session, startDate, endDate, token, dataSource, maxRetries):
    # 与 DolphinDB 建立会话和连接
    s = ddb.session(session["host"], session["port"], session["username"], session["password"])
    # 初始化库表：沪深股票 - 行情数据 - 日线复权行情（前复权）
    scripts = """
    use DolphinDBModules::EasyTushare::createDBTB
    createStockDailyPrev()
    """
    #s.run(scripts)
    dbname = s.run("getDBname('{}')".format(dataSource))  
    # 初始化python写入接口
    appender = ddb.TableAppender(dbPath='dfs://'+dbname, tableName=dataSource, ddbSession=s)
    pro = ts.pro_api(token)

    ts_codes = pro.stock_basic(list_status='L', fields=['ts_code'])

    for ts_code in ts_codes['ts_code'].values:
        get_data(ts_code, appender, startDate, endDate, token, dataSource, s, maxRetries)

    logger_stock_daily_prev.info("The %s data import is complete.", dataSource)