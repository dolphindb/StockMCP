'''
Author: tanhua hua.tan@dolphindb.com
Date: 2025-10-21 16:22:33
LastEditors: tanhua hua.tan@dolphindb.com
LastEditTime: 2025-10-22 12:00:29
FilePath: \PythonModules\TushareToDDB\dataSource\stock_basic.py
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
logging_stock_basic = logging.getLogger('logging_stock_basic')
logging_stock_basic.setLevel(logging.INFO)
# 日志输出到文件
fileHandler_stock_basic = logging.FileHandler(basic.logDir + "/stock_basic.log")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fileHandler_stock_basic.setFormatter(formatter)
# 日志输出到控制台
console_stock_basic = logging.StreamHandler() 
console_stock_basic.setFormatter(formatter)
# 将 Handler 添加到 Logger
logging_stock_basic.addHandler(fileHandler_stock_basic)
logging_stock_basic.addHandler(console_stock_basic)

def main(session, startDate, endDate, token, dataSource, maxRetries):
    # 与 DolphinDB 建立会话和连接
    s = ddb.session(session["host"], session["port"], session["username"], session["password"])
    # 初始化库表：沪深股票 - 基础数据 - 股票列表
    scripts = """
    use DolphinDBModules::EasyTushare::createDBTB
    createStockBasic()
    """
    #s.run(scripts)
    print("token:", token)
    dbname = s.run("getDBname('{}')".format(dataSource))  
    logging_stock_basic.info("The %s data import is .", dbname)
    # 初始化python写入接口
    appender = ddb.TableAppender(dbPath='dfs://'+dbname, tableName=dataSource, ddbSession=s)

    pro = ts.pro_api(token)

    retry_count = 0  # 初始化重试计数器
    max_retries = maxRetries  # 最大重试次数
    while retry_count < max_retries:
        try:
            data = pro.stock_basic(list_status='L', fields=["ts_code", "symbol", "name", "area", "industry", "market", "list_date", "act_name", "act_ent_type"])
            data = data[["ts_code", "symbol", "name", "area", "industry", "market", "list_date", "act_name", "act_ent_type"]]
            data['list_date'] = pd.to_datetime(data['list_date'], format='%Y%m%d')
            data['update_time'] = datetime.now()
            appender.append(data)
            logging_stock_basic.info("The %s data import is complete.", dataSource)
            return
        except Exception as e:
            retry_count += 1
            s.run('writeLogLevel(ERROR, "'+'easyTushareImport - '+dataSource+' - Failed to get data of '+dataSource+'. Will retry in 10 seconds. Error: '+str(e).replace('"',"'")+'")')
            logging_stock_basic.error("Failed to get data of %s. Will retry in 10 seconds. Error: %s", dataSource, e)
            time.sleep(10)
    # 如果达到最大重试次数，记录错误并抛出异常
    logging_stock_basic.error("Failed to get data of %s after %d attempts. Exiting.", dataSource, max_retries)
    raise Exception(f"Failed to get data of {dataSource} after {max_retries} attempts. Exiting.")