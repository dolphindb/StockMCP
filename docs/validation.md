# 部署验收记录

验证日期：2026-09-22。

## 环境与结果

- Linux x86_64，DolphinDB 3.00.6（2026.07.07），Python 3.12.13，DolphinDB Python SDK 3.0.6.0。
- 在独立测试实例完成建库、安装依赖函数、注册全部 21 个 MCP 工具。
- 重复安装保留已有数据：15,300 条因子观测、34 条因子元数据。
- 使用 10 只合成股票、45 个交易日运行全部 21 个工具，覆盖查询、选股、因子评价、回测、CSV 导出和清理。
- 原生 HTTP MCP 完成 initialize、tools/list 和 tools/call。
- 实例重启后，无需重新安装即可调用已发布工具；共享内存结果需要重新生成。
- 11 项自动化测试通过，包括财报公告时间对齐、历史修订、无效分母、导入分页和错误传播，以及服务端分层净值逐项对照、回测默认配置持久化。
- 分层净值回归使用每日反转的股票因子排序，与 Python 独立计算的五组净值逐项比较。

## 复现

按 README 安装并导入合成样例后执行：

```sh
python scripts/smoke.py
python -m pip install -r requirements-dev.txt
STOCKMCP_TEST_SERVER=1 python -m pytest -q tests
```

仅运行不连接数据库的测试时，不设置 STOCKMCP_TEST_SERVER。
服务端测试要求专用合成样例实例，不应对业务实例运行。

## 验证边界

使用有效 Token 完成下述小样本真实数据全链路验收。验证只覆盖列出的证券、时间、接口和字段，不代表全市场长历史、所有选配数据源或其他账户权限都已验证。

默认因子检索采用本地文本特征相似度，不依赖 GPU 或外部模型，也不等同于原内部环境的预训练语义向量模型。原始内部实现依赖 GpuLibTorch、模型与词表文件；这些模型资产不包含在本仓库中。

合成行情与回测仅用于功能回归，不用于评估投资收益。其他 DolphinDB 版本和大规模全市场数据尚未在此次验收中覆盖。

## 真实数据验收结果

- 6 只股票：600519.SH、000001.SZ、600000.SH、600036.SH、000858.SZ、601318.SH。
- 2025-09-01 至 2025-09-12，共 10 个交易日；60 条日行情、2,040 条因子观测、34 个因子。
- 贵州茅台 10 日行情的 open/high/low/close/pre_close/vol/amount 共 70 个值与重新请求的 Tushare 数据一致；60 条 PE 因子与原始每日指标一致。
- 对全部 6 只股票重新请求三张财报的键，确认与落库键集合完全一致：利润表 623 条、资产负债表 402 条、现金流量表 489 条（按完整键去重后的行数，接口原始返回可含重复记录）。
- ROE、净利率、资产负债率、利润同比均有 60 条非空观测；这验证数据覆盖，不是对全部财务数值的独立审计。
- 21 个 MCP 工具及原生 HTTP MCP 通过；查询类响应额外检查非空，选股得到 6 只股票，因子评价及回测输出有限数值。
- 个股资金流覆盖 10 个交易日；扩展基础信息及行业资金流验收使用 2025-09-01。
- 真实测试发现并修复：股票代码过滤误伤行业数据、季度财报键覆盖同日不同报表、指数行情重复导入累积。修正冒烟测试的资产负债表参数名，并增加非空检查。
- 原始财报表采用旧键时会丢失部分记录。安装器拒绝旧财报键及旧指数行情 ALL 策略；不会自动删除用户表。需要新实例重新导入，详见部署说明。

## 真实数据验收复现

使用不含合成数据的独立实例，设置 DDB_* 和 TUSHARE_TOKEN 后：

```sh
python scripts/install.py
python scripts/import_tushare.py --start 20250901 --end 20250912 \
  --codes 600519.SH 000001.SZ 600000.SH 600036.SH 000858.SZ 601318.SH
python scripts/import_tushare.py --start 20250901 --end 20250912 \
  --codes 600519.SH 000001.SZ 600000.SH 600036.SH 000858.SZ 601318.SH \
  --sources moneyflow stock_index_basic
python scripts/import_tushare.py --start 20250901 --end 20250901 \
  --codes 600519.SH 000001.SZ 600000.SH 600036.SH 000858.SZ 601318.SH \
  --sources stock_info moneyflow_ind_ths
python scripts/factors.py --start 2025-09-01 --end 2025-09-12
python scripts/validate_live_data.py
python scripts/validate_live.py
```

这两个验证脚本使用上述固定证券和日期作为验收样本，不能用于任意股票池。
`validate_live_data.py` 再次读取上游日行情，对照量价字段，并验证重复导入不增加主键行数。
验收输出保存到 `artifacts/live_reconciliation.json` 与 `artifacts/live_smoke.json`。
