# 本地部署与升级

## 环境

- DolphinDB Server：本仓库使用 3.00.6 Linux x86_64 验收。原生 MCP 自 3.00.4 起提供，但不能把“原生 MCP 的最低版本”当作本仓库所有函数的已验证最低版本。
- Python 3.10+、requirements.txt 中的客户端依赖。本次验收另有 Python 3.12 的全新虚拟环境。
- 有效 DolphinDB license，管理员或具有建库、函数视图和 MCP 开发/发布权限的部署账户。
- 服务端可写的 modules 和导出目录。数据表实际位于 DolphinDB Server，不要求 Python 与数据库在同一机器。

保持官方发行包完整，尤其不能清空 `dolphindb.dos`（包含分布式聚合的 map-reduce 定义）。`newValuePartitionPolicy=add` 用于扩展因子表日期分区；示例配置已包含。不要覆盖其他业务实例的配置和启动脚本。

## 安装顺序

1. 安装并启动 DolphinDB Server，参考仓库配置示例。
2. 安装 Python 依赖，设置 `DDB_HOST/DDB_PORT/DDB_USER/DDB_PASSWORD` 环境变量；`.env.example` 是字段示例，脚本不会自动执行 `.env` 文件。
3. 执行 `python scripts/install.py`。它完成原始库表、配置/元数据表、本地检索函数、`getDBname` 函数视图、基础元数据和全部 MCP 工具的安装。
4. 空实例运行 `load_demo.py` 和 `smoke.py`，或者在真实实例运行 `import_tushare.py` 和 `factors.py`。
5. 获取 ticket 并连接 MCP 客户端。

安装器把唯一的 schema 源文件 `建库建表/ddl.dos` 安装到服务端 `modules/DolphinDBModules/EasyTushare/createDBTB.dos`。`utils.dos` 一并提供用于旧 EasyTushare 调用；新的 schema 不再依赖该外部模块。Linux 路径区分大小写，使用 **EasyTushare/createDBTB.dos**。

`Tushare数据导入/CreateDBTB.dos` 只保留兼容加载入口，避免两份 DDL 持续分叉。旧的自动导入入口仍保留，失败会返回非零退出码；推荐新入口，其分页、列对齐和依赖顺序均可测试。

## 数据保护与升级

新 `createDB()` 和每个建表函数只创建不存在的对象，不执行删库。重复安装会更新本仓库内置因子说明和工具定义，保留行情、配置和其他因子。没有隐式的 schema 迁移：若已有同名库表采用不同结构，应先备份并核对结构，在独立实例验证升级，不要直接改生产表。

正式配置表统一为 `dfs://config/backtest_config`。旧 `backtest_config_test` 不会被删掉或自动迁移；需要继续使用旧策略时，应核对字段后显式导入正式表。

MCP 工具和 `getDBname` 函数视图持久化。重启后无需重新注册工具；共享内存结果表不会持久化，需重新运行选股/评价。历史回测配置中引用的内存股票池同理：重新产生同名结果表后才可继续使用。服务器重启或 ticket 过期时重新取得 ticket。

## MCP 客户端

```json
{
  "mcpServers": {
    "StockMCP": {
      "type": "streamableHttp",
      "url": "http://127.0.0.1:8848/mcp",
      "headers": { "Authorization": "Bearer REPLACE_WITH_YOUR_TICKET" }
    }
  }
}
```

客户端字段名称可能不同，以客户端的 Streamable HTTP 设置为准。ticket 由自己的数据库签发，不需要申请线上 Stock MCP 的 token；数据库 ticket 和 Tushare token 是两种不同凭据。按 DolphinDB MCP 使用指南配置目标用户的 MCP_EXEC、库表读取等权限。上述快速开始使用管理员用于验证，面向不受信任调用方的权限隔离需另行配置。

## 导出

默认写入服务端 `<getHomeDir()>/stockmcp_exports/`，返回真实的绝对路径。通过 SSH/SCP 获取文件即可，不需要下载 Web 服务。

若已有受控的文件下载服务，将该目录映射到自己的 URL，设置 `STOCKMCP_EXPORT_URL=https://your-host/exports` 并再次运行安装器。安装器只保存 URL，不替你部署或开放 HTTP 文件服务。无需旧代码中硬编码的服务器和端口；因子评价也返回 CSV 输出，不再指向不存在的旧报告网页。

## 常见错误

- `Cannot recognize getDBname / get_factor_metas_by_rag`：应先完整运行 install.py，不能只粘贴单个工具脚本。
- `Can't find module`：检查服务端模块路径和 Linux 大小写，重新运行安装器。
- 分布式 `max/sum` 提示无 map-reduce：检查是否保留官方 `dolphindb.dos` 并正常启动。
- 找不到因子数据：原始行情不会自动变成因子数据，导入后运行 factors.py。
- Tushare 无权限/限流：按账户权限选择数据源并增加 `--pause`；失败不会被记为成功。
- 返回的是服务器文件路径：未配置下载服务时这是预期行为。
