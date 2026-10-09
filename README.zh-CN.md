# SkillRover · 技能领航

**帮助智能体发现、选择并使用合适的技能，并定期重新评估。**

[English](README.md) · [生命周期说明](references/lifecycle.md) · [平台接入](references/integration.md)

SkillRover 本身是一个可安装的 Agent Skill。智能体先比较已经安装的技能，缺少能力时再搜索 GitHub，读取候选技能的实际内容，选择必要的组合并验证任务结果。

可选的 Python 工具负责计时、状态记录、内容校验和旧技能退役。语义判断由宿主智能体完成，不需要另一个模型 API。

## 安装到项目

需要 Python 3.10+。以下命令中的项目路径替换为你的实际路径：

```bash
git clone https://github.com/yangyanlei-jiang/skill-rover.git
cd skill-rover
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/rover.py --state-dir /你的项目/.skill-rover integrate --project /你的项目 --host both
```

仅接入一种宿主时用 `--host codex` 或 `--host claude`。Windows 使用 `.venv\Scripts\python.exe`，创建链接需要相应权限；尚未完成 Windows 宿主实机验证。保留这份克隆和虚拟环境，生成的 hook 使用它们的绝对路径。

`integrate` 的默认状态目录是目标项目下的 `.skill-rover`；其他命令默认使用当前目录。后续操作建议始终传入同一个绝对 `--state-dir`。

命令保留原来的项目配置，并加入每轮任务的技能需求判断和到期检查。按宿主要求检查并信任 hook；如果宿主未检测到变更，重启会话。

接入后正常描述任务即可，例如“分析支付流程的并发问题并补充测试”。复杂、多步骤或需要专门能力的任务会收到 SkillRover 路由指引；智能体优先检查已安装技能，缺少能力时再搜索外部候选。选中的技能通过 `use` 完成检查后的授权登记与加载，从首次加载开始计时。简单问答可以不使用技能。

无需每次手动输入技能名称；显式调用仍可作为补充入口：Codex 用 `$skill-rover`，Claude Code 用 `/skill-rover`。也可以用已有技能安装器安装根目录 skill；只有文字指引不需要 Python，持久登记和事件检查需要上述工具与 hook。

自动入口由 hook 提供指引，语义选择和实际登记由宿主模型执行，并非强制执行器。`status` 显示检查次数、待完成路由、选择/无需技能/受阻原因，以及已加载技能的下次复评时间。原生调用没有经过登记时，不会计入托管记录；“0 个托管技能”不能解释成“没有调用过任何技能”。

## 重评估周期

默认 **首次加载后 24 小时**，可通过 `use --review-hours` 或 `install --review-hours` 为每个托管技能配置。重复加载不会重置截止时间；一次真正完成的比较会开启下一周期。任务目标变化或执行失败可以立即申请重评估。

24 小时是工程默认值，不是经过统计证明的最佳周期。它适合每天重新检查长期使用的技能，同时避免每几分钟重复搜索。稳定的工作流可以使用 168 小时，频繁试验时可以使用 1 小时，再根据实际收益与成本调整。

**检查发生在宿主事件到来时。** 智能体关闭或空闲时不会自行唤醒；下次开始会话、提交任务或完成工具调用时，会检查到期技能。网络不可用或搜索失败时保留当前技能，并保持待评估状态。

## 新旧技能切换

1. 对照当前任务比较候选，确认工具、依赖和调用权限适用。
2. 实际验证新技能，保存绑定新旧技能 ID 与内容哈希的证据。
3. 等待使用旧技能的任务结束，释放会话占用。
4. 执行替换，将旧托管副本移出可用目录并归档；保留恢复所需文件。

自动卸载只针对 SkillRover 自己安装的副本。用户原始技能目录、手动安装的全局技能和 router 本身都不会被删除。归档也不能抹除模型已经读过的聊天上下文；智能体需要在任务边界停止继续使用旧指令。

同名技能用来源与路径区分；显式调用限制不能通过直接读取文件绕过；普通问答允许不使用 skill。

## 常用命令

```bash
python scripts/rover.py scan /你的技能目录
python scripts/rover.py search "pdf table extraction"
python scripts/rover.py --state-dir /你的项目/.skill-rover due
python scripts/rover.py --state-dir /你的项目/.skill-rover status
python scripts/rover.py --help
```

完整使用步骤与替换证据格式见 [生命周期说明](references/lifecycle.md)。外部技能发现与检查流程见 [外部发现](references/discovery.md)。

## 验证

```bash
python -m unittest discover -s tests -v
python examples/lifecycle_demo.py
```

测试覆盖时间边界、重复加载、正在使用的技能、内容变化、替换验证失败、归档恢复、恶意压缩包与配置保留。行为评测区分“程序机制通过测试”与“智能体原生调用成功”，不会把尚未执行的评测写成效果结论。

项目采用 MIT 许可证；不收集遥测，不内置另一个模型服务。
