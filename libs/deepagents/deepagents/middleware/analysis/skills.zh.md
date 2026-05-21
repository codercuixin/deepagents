# `skills.py` 分析

## 职责定位

`SkillsMiddleware` 扫描一个或多个 skills source，只把技能 metadata 注入 system prompt。完整 `SKILL.md` 正文由模型在需要时通过 `read_file` 读取，这就是 progressive disclosure。

## 运行流程

1. 初始化时校验 prompt 模板包含 `{skills_locations}`、`{skills_load_warnings}`、`{skills_list}`。
2. source 被拆成路径列表 `sources` 和展示标签 `source_labels`。
3. `before_agent()` / `abefore_agent()` 只在 `skills_metadata` 不存在时扫描 backend。
4. 每个 source 先 `ls` 找子目录，再批量下载子目录下的 `SKILL.md`。
5. `_parse_skill_metadata()` 只解析 YAML frontmatter。
6. 同名技能以 `name` 为 key 覆盖，后面的 source 优先。
7. source 级错误可恢复，记录到 `skills_load_errors`，随后被截断和转义后放入 prompt。
8. `modify_request()` 渲染 locations、warnings 和 skills list。

## metadata 边界

- `name`、`description` 是必填字段。
- `license`、`compatibility`、`metadata`、`allowed-tools`、`module` 是可选字段。
- `allowed-tools` 只是给模型看的建议，不会限制实际工具列表。
- `module` 只做路径校验和 metadata 传递，本 middleware 不执行 JS/TS。
- `MAX_SKILL_FILE_SIZE` 限制的是 `SKILL.md` 解析输入，不限制辅助文件大小。

## 安全设计

- skill 正文不直接进入 prompt，减少无关上下文和 prompt 注入面。
- load warnings 作为不可信诊断展示，并做 JSON 化、HTML escape 和长度截断。
- `module` 禁止绝对路径和 `..` 逃逸，避免后续消费方加载技能目录外文件。

## 维护注意

- sync/async 扫描规则必须保持一致。
- 空 `skills_metadata` 也表示已经扫描完成，不能反复 I/O。
- 修改 source label 派生规则时要注意历史 prompt 输出兼容。
- 如果未来要把 `allowed-tools` 变成强制约束，应放在工具过滤/权限层，而不是只改 metadata 渲染。
