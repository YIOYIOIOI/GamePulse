# 运行手册

以下命令都在项目根目录执行。服务只监听 127.0.0.1；数据默认写入 `var/`，可用环境变量 `GAMEPULSE_DATA_DIR` 改到其他目录。

## 启动

```powershell
.venv\Scripts\python.exe -m src.quality.cli serve --port 8767
```

本机单人模式下不需要登录，所有操作都以本地管理员身份执行。

## 添加游戏

在侧边栏或「设置 → 游戏」点「添加游戏」，按名称或 App ID 搜索 Steam，可选关联 GitHub 仓库。命令行等价操作：

```powershell
.venv\Scripts\python.exe -m src.quality.cli game add <Steam App ID> --repo <owner/name>
.venv\Scripts\python.exe -m src.quality.cli game list
.venv\Scripts\python.exe -m src.quality.cli game remove <游戏 key>
```

App ID 是商店页链接里的数字，例如 store.steampowered.com/app/**1127400**。游戏 key 由名称生成（英文名转小写，中文名为 `app-<App ID>`），`game list` 可以查看。添加、修改仓库和移除游戏需要管理员权限。

## 同步数据

在顶部或「设置 → 数据源」点「同步数据」，或用命令行：

```powershell
.venv\Scripts\python.exe -m src.quality.cli sync --days 180                       # 全部已添加的游戏
.venv\Scripts\python.exe -m src.quality.cli sync --products <游戏 key> --days 90    # 只同步某几款
```

- 同步通常需要 2–5 分钟。完成前界面继续显示上一份数据，失败的同步不会覆盖已有结果。
- 每款游戏显示最近一次包含它的同步结果，单独同步一款游戏不会影响其他游戏。
- 规则或指标更新后，用「重新计算」或下面的命令，基于已存档的原始数据重算，不重新抓取：

```powershell
.venv\Scripts\python.exe -m src.quality.cli replay <快照编号>
.venv\Scripts\python.exe -m src.quality.cli verify            # 校验最新快照的全部原始页哈希
```

快照编号在「设置 → 数据源 → 同步记录」里可以看到。

## 团队模式

```powershell
.venv\Scripts\python.exe -m src.quality.cli member --name 张三 --role owner
.venv\Scripts\python.exe -m src.quality.cli serve --port 8767 --team
```

- `member` 只输出令牌文件的位置，令牌明文不会出现在命令行或接口响应里；数据库只保存令牌哈希。把令牌文件交给成员本人，成员在界面右上角「登录身份」里填入。令牌只保存在当前浏览器标签页。
- 管理员也可以在「设置 → 成员与权限」添加和停用成员。
- 工作区（`--workspace`，默认 `main`）之间的跟进和 AI 会话互相隔离。备份涉及整个数据库，只有 `main` 工作区的管理员可以操作。

| 角色 | 权限 |
|---|---|
| 只读 viewer | 查看全部页面和跟进，导出数据 |
| 分析员 analyst | 另外可以创建跟进、更新调查进展、使用 AI 助手 |
| 复核人 reviewer | 另外可以把跟进标为「已确认」或「已关闭」 |
| 管理员 owner | 另外可以同步数据、管理成员、创建备份 |

### 企业单点登录（OIDC）

团队模式可以直接接受企业身份服务签发的 Bearer 令牌：

| 环境变量 | 说明 |
|---|---|
| `GAMEPULSE_OIDC_ISSUER` | 必填，HTTPS 地址 |
| `GAMEPULSE_OIDC_AUDIENCE` | 必填 |
| `GAMEPULSE_OIDC_JWKS_URL` | 可选，默认 issuer 下的 `/.well-known/jwks.json` |
| `GAMEPULSE_OIDC_WORKSPACE` | 可选，默认 `main` |
| `GAMEPULSE_OIDC_GROUP_ROLES` | 企业用户组到角色的 JSON 映射，例如 `{"qa-leads": "reviewer"}`；没有匹配的用户组时为只读 |

服务校验签名（RS256 / ES256）、有效期、issuer 和 audience。角色只从服务端配置的用户组映射得出，不信任令牌里自带的角色字段。目前界面没有实现跳转式登录，令牌需要由企业门户或网关提供。

## 多进程运行

```powershell
$env:GAMEPULSE_PORT = '8767'
$env:GAMEPULSE_TEAM = '1'
.venv\Scripts\python.exe -m uvicorn src.quality.server:build --factory --workers 2 --host 127.0.0.1 --port 8767
```

多个进程共用同一个本机数据库，通过任务租约协调同步、AI 分析和备份；这不是跨主机的分布式部署。

## AI 助手

需要本机安装并登录 Codex CLI（`codex login`）。未安装或未登录时，AI 助手面板会显示原因，其他功能不受影响。提问和选中的反馈会发送给 Codex 配置的模型服务。

## 备份与恢复

在「设置 → 备份」点「立即备份」，或：

```powershell
.venv\Scripts\python.exe -m src.quality.cli backup
.venv\Scripts\python.exe -m src.quality.cli restore-drill <备份编号>
```

备份保存在 `var/backups/<备份编号>/backup.zip`，包含一致性数据库副本和全部原始响应，附逐文件 SHA-256 清单，不包含访问令牌。`restore-drill` 把备份恢复到 `var/recovery/` 下的新目录，逐项校验文件哈希、数据库完整性和最新快照指纹，不影响正在使用的数据。需要正式恢复时，先停止服务，再用恢复目录里的 `warehouse.sqlite3` 和 `raw/` 替换数据目录中的同名文件。
