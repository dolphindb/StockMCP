# Stock MCP

DolphinDB 原生 MCP 股票投研工具：指标检索、选股、因子评价、策略回测，以及行情、财报、资金流查询。本仓库提供 21 个工具、完整初始化入口、Tushare 导入、因子加工和离线样例验收。

- [本地部署与升级](docs/local_deployment.md)
- [数据口径、数据源和更新流程](docs/data_pipeline.md)
- [验收与已知限制](docs/validation.md)
- [官网介绍](https://docs.dolphindb.cn/zh/mcp/stock_mcp.html)
- [DolphinDB MCP 使用指南](https://docs.dolphindb.cn/zh/mcp/mcp_use_guide.html)

## 五步运行离线样例

先部署带有效 license 的 DolphinDB Server。推荐本仓库实测的 **3.00.6**，保留发行包的 `dolphindb.dos`、动态库和 `marketHoliday`。单机配置参考 [deploy/dolphindb.cfg.example](deploy/dolphindb.cfg.example)。使用全新的独立实例运行样例。

```bash
# Python 3.10+；下面以 Linux/macOS 为例。
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

export DDB_HOST=127.0.0.1
export DDB_PORT=8848
export DDB_USER=admin
# 使用自己的密码；避免把密码提交到仓库。
read -s DDB_PASSWORD
export DDB_PASSWORD

python scripts/install.py
python scripts/load_demo.py
python scripts/smoke.py
```

`install.py` 保留已有数据库和数据，可重复执行。`load_demo.py` 生成明确标记的**合成数据**，不需要 Tushare Token；若实例已有真实行情，会拒绝混入样例。`smoke.py` 验证全部工具和原生 HTTP MCP，结果保存到 `artifacts/smoke.json`。

MCP 客户端地址为 `http://<DDB_HOST>:<DDB_PORT>/mcp`，传输方式为 Streamable HTTP。登录 DolphinDB 后运行 `getAuthenticatedUserTicket()` 获取当前账户 ticket，设置 `Authorization: Bearer <ticket>`。不需要另起一个 Python MCP Server。

真实数据部署请使用独立实例，按[数据流程](docs/data_pipeline.md)导入、加工后再连接客户端。
