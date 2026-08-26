# ListenTrace M13 UI DNA 设计决策与落地规范

## 1. 核心定位与设计哲学

ListenTrace 是一款**本地优先（Local-First）的专业级外语听力精研与语音诊断桌面工作台**。

在 Milestone 12 Phase 12-A（底层产品功能加固与契约验证）完成后，UI 层面仍存在典型的 Qt 控件堆叠感（平铺按钮、边界框嵌套过密、主次任务层级模糊、学习专注度不足）。本次 HTML 原型确立了面向 **Milestone 13（Advanced UI/UX Reconstruction）** 的全新 **UI DNA**：

> **外层：严谨高效的专业生产力工作台（Airtable / Linear 结构感）**  
> **听音时：沉浸聚焦的暗色视听舞台（Focused Cinema Media Stage）**  
> **研读/回忆时：宁静舒缓的纸质学习画布（Paper-like Study Canvas）**

---

## 2. 界面三重形态（The Three Surface Modes）

| 界面形态 | 应用场景 | 视觉与交互特征 | 体验目标 |
|---|---|---|---|
| **1. 生产力工作台 (Workspace)** | 素材资料库、全局学习历史、凭证导出 | 柔和背景、结构化数据表格、右侧详情抽屉、清晰的主次动作栈 | 提供快速管理、状态检索与一键启动训练的专业桌面操作体验 |
| **2. 沉浸视听舞台 (Focused Cinema Stage)** | 播放器、快速选句练习、听音复听 | 深色背景（`#121418`）、暗光居中视听窗、高对比度波形指示、循环缓冲（200ms Grace）显性胶囊 | 屏蔽外界干扰，使学习者的注意力 100% 聚焦于语音流与声学细节 |
| **3. 纸质研读画布 (Paper Study Canvas)** | 听写比对归因（Stage 3）、影子跟读（Stage 4）、回忆重构（Stage 5） | 暖白/哑光纸质底板（`#FAF8F4`）、类书卷衬线/非衬线排版、柔和卡片投影、大字距段落 | 营造“书桌式”安静研读氛围，减少数字界面的视觉侵略感 |

---

## 3. 动作语法与按钮层级系统（Action Hierarchy Grammar）

为了根治旧版“全屏同等权重按钮”的问题，M13 原型建立了严格的动作语法：

1. **Primary（主推前进动作）**：
   - 视觉：暖陶土橙主色（`#E8794F` / 暗色模式 `#F08C65`），微投影，字重 600。
   - 规则：**每个界面或主卡片中严格只允许存在 1 个 Primary 按钮**（如 `▶ 继续精听训练`、`保存归因并进入下一句`、`完成并封存`）。
2. **Secondary（次级支撑动作）**：
   - 视觉：白底/浅色底，描边为默认中性线（`--border-default`），文本深墨色。
   - 规则：用于平级备选路径（如 `⚡ 开启快速练习`、`🎙️ 影子跟读`、`🐢 0.8x 慢速重听`）。
3. **Quiet / Ghost（轻量工具动作）**：
   - 视觉：无背景无描边，悬浮时激活微妙浅灰（`--bg-hover`），不抢夺视线。
   - 规则：用于辅助操作、过滤切换、单句跳过、关闭弹窗。
4. **Danger（破坏性动作）**：
   - 视觉：浅淡红底搭配深红文字（`--color-danger-subtle`），仅在悬停时变红实底。
   - 规则：用于 `🗑️ 从资料库移除素材`、`放弃本次会话`。严禁在常规状态下使用刺眼的实心大红按钮。
5. **Disabled（不可用状态）**：
   - 视觉：透明度降至 0.45，鼠标指针为 `not-allowed`，附带清晰的 Tooltip 或状态文案解释不可用原因。

---

## 4. 去除“框框杂乱”（Eliminating Box-Clutter）

旧版 Qt 界面过度依赖 `QGroupBox` 与四周边框，导致用户视线被大量线条切割。本原型采用以下现代界面排版手法取代线条：
- **色块与底板分层（Tonal Surface Layering）**：使用 `--bg-app`（暖米底）、`--bg-surface`（纯白卡片）、`--bg-surface-soft`（柔和嵌板）进行视觉分组。
- **空白韵律（Whitespace & Spacing Scale）**：通过 4px / 8px / 16px / 24px / 32px 的严谨等比间距形成自然的视觉亲和力。
- **层次轻投影（Subtle Elevation）**：卡片与纸质书卷仅保留微弱阴影（`0 4px 12px rgba(0,0,0,0.06)`），替代生硬的黑灰外边框。

---

## 5. 多通道状态通信（无障碍色彩独立性）

严格遵循可访问性标准，所有关键状态均通过 **多通道（Multi-channel）** 进行表达，绝不单独依赖单一色彩：
- **播放中句段**：暖黄高亮背景 + 左侧金橙高亮指示条 + 标题文字前缀 `▶` + `正在播放` 文字胶囊。
- **比对差异项**：
  - 误听/多听词：红底 + 红色文字 + **删除线（Strikethrough）**。
  - 漏听/考点词：金黄底 + 褐色文字 + **加粗（Bold）**。
  - 正确匹配：绿色底 + 浅绿文字。
- **测验选项卡**：单选圆点（Radio Indicator）+ 外框加粗 + 背景变色 + 全量自动换行（彻底解决旧版 `QRadioButton` 文字截断缺陷）。

---

## 6. 原型六大核心视图书签解析

1. **素材资料库 (Material Library)**：
   - 展现了从“素材列表”到“右侧动作指挥台”的顺畅过渡，清晰呈现 5 阶段状态进度、200ms Grace 校准参数与操作层级。
2. **聚焦播放与快速练习 (Synchronized Player & Quick Practice)**：
   - 实现了深色视听台（Cinema Stage）与右侧句段字幕导航（Cue Navigator）的联动，集成 200ms 循环尾部补偿指示、波形游标、快速选句入口。
3. **听写比对与错误归因 (Transcript Comparison & Diagnosis)**：
   - Stage 3 核心画布：上部为 5 阶段进度 Stepper，中部为 Diff 逐词比对区，下方集成 5 大维度听音障碍分类标签（连音/吞音、生词、句法、语速、声学干扰）与学习心得笔记本。
4. **句子级影子跟读 (Sentence-Level Shadowing)**：
   - Stage 4 跟读平台：突出“大录音触发台”与“多 Take 版本管理”，严格落地 **原声 vs 录音“顺序对比播放（原音 -> 停顿500ms -> 录音）”** 的底层契约，杜绝声音混叠。
5. **回忆重构与总结 (Final Recall & Synthesis)**：
   - Stage 5 沉浸式笔记本：采用纸质书写台排版，右侧悬浮显示前 4 个阶段沉淀的重点归因证据与最佳录音 Take，点击完成提供明确的封存语义说明。
6. **智能检索与测验 (Quiz & Retrieval Practice)**：
   - 考点原声重听控制器、大字体题干、支持长文本自动换行的卡片式单选项、原子化提交批改流。

---

## 7. 向 Milestone 13 (PyQt6) 实施阶段的技术映射方案

| 原型 HTML/CSS 特性 | PyQt6 / QSS 映射方案 |
|---|---|
| CSS 变量系统 (`:root`, `[data-theme="dark"]`) | 扩展 `src/listentrace/ui/theme.py`，维护统一的 Light / Dark Token 映射字典与 `qcolor()` 转换函数 |
| 按钮角色（`btn-primary`, `btn-secondary` 等） | 统一通过 `widget.setProperty("role", "primary")` 声明，并在 `theme.py` 组件层样式表中统一定义 |
| 纸质研读卡片（`.paper-sheet`） | 自定义 `QFrame[role="paper-sheet"]` 或封装 `PaperStudySurface` 复合控件 |
| 沉浸播放舞台（`.cinema-stage`） | 在 `PlayerWindow` 中将视听区容器设置为专属 dark QSS 样式表，与外围主窗体解耦 |
| 自动换行测验选项卡（`.quiz-option-card`） | 使用继承自 `QFrame` 的可点击选项卡控件，内置 `QLabel`（开启 `wordWrap=True`）与自定义指示器，彻底摒弃原生 `QRadioButton` |
| 录音与波形可视化 | 继承现有的 `RecordingPanel` 与 `SimpleBarChart`，统一接入 `theme.py` 的 Semantic Tokens |
