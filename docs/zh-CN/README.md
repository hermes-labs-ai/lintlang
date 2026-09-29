# LintLang 简体中文快速上手

> **English 版 [README.md](../../README.md) 是权威文档。** 本页只是精简的中文入门，若与英文内容不一致，以英文为准。检测规则和精确行为见[技术参考](../../llms-full.txt)。
> 版本号不在本页硬编码：以 `pyproject.toml` 中的 `version` 字段和 `lintlang --version` 的输出为准（英文 README 顶部的 PyPI 徽章显示已发布版本）。

## LintLang 是什么

LintLang 是一个本地运行、结果确定的静态检查工具，检查对象是交给 AI 智能体的指令和工具接口。它会在智能体运行之前，指出工具选择有歧义、要求相互冲突、schema 缺口、缺少边界约束等配置问题。

它能在你已有的文件里找到受支持的、面向智能体的内容，包括：

- JSON/YAML 中嵌套的 MCP 和 function-tool 工具描述，以及参数 schema
- 系统提示词、messages、输出约定，以及 `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、`SKILL.md`
- 受支持的 Python 提示词代码

典型问题包括：

- **工具描述有歧义**：同级工具功能重叠，模型没有明确理由选其一
- **缺少边界**：重试、循环或工具调用没有明确的停止或进展条件
- **schema 不匹配**：缺少必填字段、参数含义不清
- **指令冲突**：输出要求互相矛盾、优先级含糊
- **SKILL.md 缺陷**：元数据缺失或无效、使用条件不清、技能名与目录名不一致
- **上下文与消息错误**：过期的项目引用、无限期持久化、角色格式错误、工具消息顺序断裂
- **内嵌逻辑**：受支持的 Python 提示词、字面量工具定义、部分流水线阈值

## LintLang 不是什么

- 不做运行时评估，不做动态的智能体测试，不运行模型，也不观察运行时的工具选择
- 不能证明智能体在生产环境中是安全的
- 不判断内容真伪，不保证任意文本语义正确，不保证与各模型提供方兼容
- 扫描期间不调用 LLM、不拉取远程规则、不发送遥测或网络请求（安装软件包本身，以及宿主集成自己的模型调用，不在此约定之内）

## 安装

需要 Python 3.10+。

不安装，直接运行一次：

```bash
uvx lintlang scan .
```

用 pip 安装：

```bash
pip install lintlang
lintlang scan .
```

macOS 上用 Homebrew：

```bash
brew install hermes-labs-ai/tap/lintlang
lintlang scan .
```

## 第一次运行

在项目目录下运行上面的 `uvx lintlang scan .`，或指定单个配置来源：

```bash
uvx lintlang scan AGENTS.md
uvx lintlang scan SKILL.md
uvx lintlang scan agent.yaml
```

如何解读结果：

- 每条结果都会说明 LintLang 实际检查了什么。
- 没有识别到任何面向智能体的结构的内容，会报告为 `SKIPPED`，绝不会报告为 `PASS`。
- 工具之间的比较只发生在同一个被解析的输入内；扫描目录时，不会把不同文件里的工具合并到同一个选择命名空间。
- 默认情况下，检查结果仅供参考，不会让命令失败。
- 扫描干净只表示：所选的静态检查在被识别的内容中没有发现所覆盖的缺陷。

## 在 CI 中作为门禁

遇到 HIGH 或 CRITICAL 级别的发现时让命令失败：

```bash
lintlang scan . --fail-on fail
```

把 MEDIUM 级别也纳入门禁：

```bash
lintlang scan . --fail-on review
```

生成固定版本的 GitHub Actions 工作流，扫描整个仓库目录：

```bash
lintlang init --github --path .
```

生成的 Action 默认对 HIGH 或 CRITICAL 级别的发现设置门禁。如果 CI 只需检查某一个配置来源，请改用更窄的路径。

对于已有历史发现的仓库，可以先记录一份经过评审的基线：

```bash
lintlang scan . --write-baseline .lintlang-baseline.json
```

之后只对新增或变更的发现设置门禁：

```bash
lintlang scan . \
  --baseline .lintlang-baseline.json \
  --fail-on review
```

更多细节见英文文档：[GitHub CI and Code Scanning](../github.md)、[baseline adoption](../baselines.md)、[GitLab CI guide](../gitlab.md)。

## 使用边界

- 这是静态检查：只检查仓库里可以在运行前审阅的、承载语言的文件。
- 检查结果是提示你去查看某个文件的依据，不代表模型一定会出错，也不代表某段文字一定有错。
- 没有发现问题，并不说明不受支持的结构被分析过。
- 它与 schema 校验、运行时评估以及领域和安全评审是互补关系，不能替代它们。
- preflight 是独立于仓库扫描的有限能力，其状态和退出语义与仓库扫描的结论分开，详见[技术参考](../../llms-full.txt)。
- 发现误报或对某条发现有异议，欢迎按 [CONTRIBUTING.md](../../CONTRIBUTING.md) 反馈；安全漏洞请遵循 [SECURITY.md](../../SECURITY.md)。
