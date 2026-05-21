# `async_subagents.py` 分析

## 职责定位

`AsyncSubAgentMiddleware` 面向远程 Agent Protocol / LangGraph server。它不阻塞等待子任务完成，而是提供一组 task 管理工具：启动、查询、更新、取消和列表。

## 工具集合

- `start_async_task`：创建远端 thread/run，并立即返回 `task_id`。
- `check_async_task`：查询远端 run 状态；成功时读取 thread values 并返回最后一条消息内容。
- `update_async_task`：在同一 thread 上 interrupt 当前 run 并创建新 run。
- `cancel_async_task`：取消当前 run，本地状态置为 `cancelled`。
- `list_async_tasks`：列出本地追踪任务并刷新 live status。

## 运行流程

1. 初始化时校验 async subagent 非空且名称唯一。
2. `_ClientCache` 按 `(url, headers)` 缓存 sync/async LangGraph SDK client。
3. `start_async_task` 创建远端 thread 和 run，本地 `task_id` 直接使用远端 `thread_id`。
4. `async_tasks` reducer 以 `task_id` 为 key 合并任务更新。
5. `check_async_task` 只能查询本地已追踪 task，再访问远端 run。
6. `update_async_task` 保持 `task_id` 不变，只更新当前 `run_id`。
7. `list_async_tasks` 先按缓存状态过滤，再获取 live status；异步路径并发刷新。
8. `wrap_model_call()` / `awrap_model_call()` 注入系统提示，约束模型启动后不要立即轮询。

## 状态模型

`AsyncTask` 记录 `task_id`、`agent_name`、`thread_id`、`run_id`、`status`、`created_at`、`last_checked_at` 和 `last_updated_at`。

`task_id == thread_id` 是有意设计：thread 是跨 run 的稳定标识，而 `run_id` 会在 update 后变化。

## 关键设计

- 默认补 `x-auth-scheme: langsmith`，LangGraph Platform 需要，自托管服务通常会忽略。
- 同一 URL 但不同 headers 不复用 client，避免认证上下文串线。
- sync SDK 不支持 `url=None` 的本地 ASGI transport，因此这种配置只适用于 async invocation。
- 工具错误大多返回模型可读字符串，而不是抛异常破坏 agent 图。
- 终态任务不再访问远端，减少列表查询的网络成本和失败面。

## 维护注意

- 新增远端 run 终态时同步更新 `_TERMINAL_STATUSES`。
- `check_async_task` 当前只取最后一条消息内容；远端 graph 需要自己把最终消息设计成可消费格式。
- `status_filter` 基于缓存状态过滤，然后刷新 live status，这是语义稳定和成本可控之间的取舍。
- 不要让工具接受任意 thread id 直接探测远端状态；本地 tracked task 是一致性边界。
