'''
Author: tanhua hua.tan@dolphindb.com
Date: 2025-10-21 16:22:33
LastEditors: tanhua hua.tan@dolphindb.com
LastEditTime: 2025-10-22 11:58:30
FilePath: \PythonModules\TushareToDDB\basic.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
'''
#!/usr/bin/env python
# coding: utf-8
import datetime
import os

# 数据导入模式
'''
全部历史数据导入: 1
当日新增数据导入: 2 (以下数据源在模式 2 中为全量导入: 'stock_basic', 'stock_daily_back', 'stock_daily_prev', 'stock_monthly_back', 'stock_monthly_prev', 'stock_name', 'stock_weekly_back', 'stock_weekly_prev')
'''
mode = 1

# tushare token
token = ""

# DolphinDB Session 配置
session = {
}

# 数据源导入日期范围，在 mode = 1 时生效
startDate = "20210101"
endDate = datetime.date.today().strftime("%Y%m%d")

# 需要导入的数据源列表

dataSourceList = [
    'stock_basic',
    'stock_premarket', 
    'stock_name',
    'stock_new',
    'stock_info',
    'stock_daily',
    'stock_weekly',
    'stock_monthly',
    'stock_daily_prev',
    'stock_daily_back',
    'stock_weekly_prev',
    'stock_weekly_back',
    'stock_monthly_prev',
    'stock_monthly_back',
    'stock_adj_factor',
    'stock_daily_basic',
    'stock_limit',
    'stock_suspend',
    'stock_daily_info',
    'moneyflow',
    'moneyflow_ind_ths',
    'quarter_stock_cashflow',
    'quarter_stock_income',
    'quarter_stock_balancesheet'.
    'year_stock_cashflow',
    'year_stock_balancesheet',
    'year_stock_income'
]
# 数据导入最大重试次数
maxRetries = 5

# 导入并行度，适用于多数据源并行导入场景
parallelism = 19

# 数据导入日志路径
logDir = os.path.dirname(__file__) + "/log/"
