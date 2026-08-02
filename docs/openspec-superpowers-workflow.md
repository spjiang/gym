# OpenSpec + Superpowers 使用流程（通用版）

面向任意软件项目的协作手册：先分清两套工具各自干什么，再按「从想法到可验收交付」走通。

---

## 1. 一句话分工

| 工具 | 一句话 | 主要产物落在哪 |
|------|--------|----------------|
| **Superpowers** | AI 协作的「做事流程技能」：想清楚 → 写计划 → 按任务实现 → 调试收尾 | 通常为 `docs/superpowers/` |
| **OpenSpec** | 仓库内的「规格与变更系统」：每次变更有提案/规格/设计/任务，做完归档进主规格 | `openspec/` |

**记住：**

- Superpowers 管 **怎么和 AI 协作推进**（对话流程与技能顺序）
- OpenSpec 管 **需求与变更如何落盘、可验证、可归档**（文件契约）
- 业务代码写在应用目录（如 `src/`、`app/`、`frontend/`、`backend/` 等），**不在** `openspec/` 里

两者可组合，也可在某一阶段只用其中一个；推荐组合见第 5 节。

---

## 2. 典型目录地图

不同仓库布局会有差异，以下是常见形态：

```
<project-root>/
├── docs/
│   ├── openspec-superpowers-workflow.md   ← 本文（可选）
│   └── superpowers/
│       ├── specs/     ← Superpowers 产出的产品/设计规格
│       └── plans/     ← Superpowers 产出的细粒度实现计划（可选）
│
├── openspec/
│   ├── config.yaml    ← 项目上下文与制品规则（给 AI 用）
│   ├── specs/         ← 「已生效」的主规格（归档后累积）
│   └── changes/       ← 「进行中」的变更
│       ├── archive/   ← 已完成变更
│       └── <change-name>/
│           ├── proposal.md   ← 为什么做、做什么、不做什么
│           ├── design.md     ← 怎么做（技术设计）
│           ├── tasks.md      ← 实现勾选清单
│           └── specs/        ← 本变更的行为要求（验收标准）
│
├── <application-code>/   ← 真正的实现代码
└── .cursor/              ← 若使用 Cursor：rules / commands / skills 等
```

### 2.1 三种「规格」别搞混

| 位置 | 含义 | 何时有内容 |
|------|------|------------|
| `docs/superpowers/specs/*.md` | 产品/设计级文档（人读为主，如 PRD、方案）；可含「交付对照表」跟踪一期进度 | brainstorming 完成后 |
| `openspec/changes/.../specs/` | **本变更**要新增或修改的行为（SHALL + 场景） | propose 时生成 |
| `openspec/specs/` | 全项目**已定稿**主规格 | archive 之后从 change 合并进来 |

口诀：**change 里是施工单；根上 `openspec/specs` 是已验收的正式规范。**

### 2.2 一条 change 优先读什么

不必先读完所有 `spec.md`，优先：

1. `proposal.md` — 范围与 Non-goals  
2. `tasks.md` — 执行清单  
3. 有争议再看 `design.md` 和 `specs/<capability>/spec.md`

---

## 3. 从零接入（任意新仓库）

### 3.1 Superpowers

在 Cursor（或支持该技能包的环境）中启用 Superpowers 插件/技能后即可使用。无需在仓库里「init」；产物建议约定落到 `docs/superpowers/`。

### 3.2 OpenSpec

```bash
# 全局安装（版本以官方为准）
npm install -g @fission-ai/openspec@latest

cd <your-project>
openspec init          # 交互选择工具；Cursor 可用 --tools cursor
```

建议随即完善 `openspec/config.yaml` 中的 `context`（技术栈、约定、领域背景）和可选的 `rules`，让后续 propose 不跑偏。

自检：

```bash
openspec list
openspec list --specs
openspec doctor        # 若可用，检查关系健康度
```

---

## 4. Superpowers：常用技能与顺序

核心链路：

```
想法模糊
  → brainstorming
  → 产出 docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
  → 人工审阅规格
  → writing-plans（可选，任务需更细时）
  → 执行计划（subagent-driven-development 或 executing-plans）
  → 遇 bug：systematic-debugging
  → 声称完成前：verification-before-completion
  → 分支收尾：finishing-a-development-branch
```

| 技能 | 什么时候用 |
|------|------------|
| `brainstorming` | 需求不清、要选型、要写设计/PRD；**先设计后写码** |
| `writing-plans` | 已有规格，需要可执行细任务（含验证步骤） |
| `executing-plans` / `subagent-driven-development` | 按计划逐项实现 |
| `systematic-debugging` | 行为异常、根因不清 |
| `test-driven-development` | 先测后码（计划中常要求） |
| `verification-before-completion` | 完成宣称前先验证 |
| `finishing-a-development-branch` | 功能做完后的分支收尾 |

技能的调用方式因环境而异（斜杠命令、技能名或「使用某某技能」）；以当前环境实际可用的入口为准。

---

## 5. OpenSpec：日常四步

常见 Cursor 命令（`openspec init --tools cursor` 后）：

| 命令 | 作用 |
|------|------|
| `/opsx-explore` | 讨论、探路，不急着落变更文件 |
| `/opsx-propose` | 一键生成 change：proposal + specs + design + tasks |
| `/opsx-apply` | 按 `tasks.md` 实现并勾选 |
| `/opsx-archive` | 完成后归档，合并进 `openspec/specs/` |

部分环境命令名可能是 `/opsx-propose` 或 `/opsx:propose` 等形式，以 init 输出与 `.cursor/commands/` 为准。

CLI 常用：

```bash
openspec list                              # 进行中的 change
openspec list --specs                      # 已生效主规格
openspec status --change <name>            # 制品是否齐全
openspec validate <name>                   # 校验 change
openspec instructions <artifact> --change <name> --json
openspec new change <name>                 # 只建空 change（一般直接 propose）
```

### 5.1 推荐节奏

```text
产品还糊？ ──是──► Superpowers brainstorming ──► 设计/PRD
     │
     否
     ▼
/opsx-propose「可验收切片」──► 人工审 proposal + tasks
     ▼
/opsx-apply ──► 改应用代码，勾 tasks
     ▼
验收通过 ──► /opsx-archive ──► 主规格更新
     ▼
下一切片，继续 propose
```

### 5.2 什么叫「一个切片」

一次 change 应能**单独演示、单独验收**。例如：

- 脚手架与健康检查  
- 某一领域的最小闭环（如「账号登录 + 基础权限」）  
- 单个用户可感知的功能增量  

避免把整期产品规划塞进一次 apply。

---

## 6. 组合用法（通用模式）

### 模式 A：新产品或大模块

1. Superpowers **brainstorming** → `docs/superpowers/specs/`  
2. 人工审阅设计/PRD  
3. 完善 `openspec/config.yaml`  
4. OpenSpec **propose** 拆成多个工程切片  
5. **apply** → **archive**，循环

### 模式 B：日常小功能（目标已清晰）

1. 直接 `/opsx-propose <描述>`  
2. 审 tasks → apply → archive  
3. 通常不必再开 brainstorming

### 模式 C：OpenSpec tasks 偏粗

1. 已有 change 的 proposal / specs  
2. Superpowers **writing-plans** → `docs/superpowers/plans/`  
3. 执行时以细计划为准，并回勾 `tasks.md`（或只维护一份，避免长期双源）

### 模式 D：实现中卡住

- 需求争议 → 改 change 的 specs/proposal，或回到 brainstorming  
- 纯技术缺陷 → **systematic-debugging**  
- 勿静默扩大 Non-goals

---

## 7. 各文件读到什么程度

| 文件 | 建议 |
|------|------|
| 本文 | 建立心智模型时通读 |
| Superpowers specs | 当产品/设计说明书；大范围变更先改它或重开 brainstorming |
| `openspec/config.yaml` | 了解其约束 AI 即可；按项目演进维护 |
| `proposal.md` | **必读**：范围与 Non-goals |
| `tasks.md` | **必读**：执行清单 |
| `design.md` | 实现前扫关键决策 |
| `changes/.../specs/*/spec.md` | 验收、争议、写测试时对照 |
| `openspec/specs/` | 归档后逐渐成为系统行为真源 |

---

## 8. 示例对话（换成你的领域即可）

**开新变更：**

```text
/opsx-propose 用户邮箱登录与密码重置
```

**开始实现：**

```text
/opsx-apply
```

**完成归档：**

```text
/opsx-archive
```

**需求再次变糊：**

```text
/brainstorming
我们要把多租户数据隔离规则想清楚，再更新规格
```

**只讨论不落变更文件：**

```text
/opsx-explore
缓存失效和强一致之间怎么取舍？
```

---

## 9. 常见误区

1. **把 `openspec/` 当成源码目录** — 那里是规格与变更；代码在应用目录。  
2. **产品文档与 OpenSpec 长期双份分叉** — 总图可放 Superpowers specs；可验证的行为增量以 OpenSpec change / 主 specs 为准。  
3. **一次 propose 范围过大** — 难以 apply 与验收。  
4. **未审 tasks 就 apply** — 容易做出 Non-goals 中的内容。  
5. **做完不 archive** — 主规格不更新，后续 propose 缺少已有行为上下文。  
6. **Rules / 设计文档 / OpenSpec 混为一谈**  
   - 编辑器 rules（如 `.cursor/rules`）= 编码习惯  
   - Superpowers specs = 产品与设计思考  
   - OpenSpec = 可归档的行为契约与变更任务  

---

## 10. 最小记忆卡

```text
想清楚  →  Superpowers brainstorming  →  docs/superpowers/specs/
要开工  →  /opsx-propose              →  openspec/changes/<name>/
写代码  →  /opsx-apply                →  应用代码目录，勾 tasks.md
做完了  →  /opsx-archive              →  openspec/specs/ 更新 + 回写 PRD 交付对照表
卡住了  →  需求：explore / brainstorming；缺陷：systematic-debugging
```

**本仓库进度入口：** PRD 未完成项看  
`docs/superpowers/specs/2026-08-02-gym-prd-modules-design.md` → **§10 一期交付对照表**。  
已落地行为契约看 `openspec/specs/`（`openspec list --specs`）。

---

## 11. 新项目自检清单

- [ ] 已安装并可用 `openspec` CLI  
- [ ] 仓库已 `openspec init`，且 `config.yaml` 写了有用的 `context`  
- [ ] 大需求先有设计/PRD（Superpowers specs），或确认可直接 propose  
- [ ] 当前 change 的 `proposal` / `tasks` 已人工过目  
- [ ] apply 只做本 change 范围；完成后 archive  
- [ ] 主规格 `openspec/specs/` 随归档持续增长  

---

## 12. 参考与版本说明

| 说明 | 去哪看 |
|------|--------|
| OpenSpec CLI | `openspec --help`；包名一般为 `@fission-ai/openspec` |
| 本仓库/本机斜杠命令 | `.cursor/commands/opsx-*.md`（若已 init） |
| Superpowers 技能说明 | 当前环境已安装的 Superpowers skills 文档 |

命令名与 schema 可能随版本变化；**以你本机 CLI 与 init 生成的命令文件为准。**
