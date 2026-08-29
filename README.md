markdown
# 🧠 RecallEngine

**记忆增强型意图路由与执行引擎** — 让 AI Agent 在“拿不准”时懂得“翻聊天记录”来确认意图。

[![PyPI version](https://badge.fury.io/py/recall-engine.svg)](https://badge.fury.io/py/recall-engine)
[![Python versions](https://img.shields.io/pypi/pyversions/recall-engine.svg)](https://pypi.org/project/recall-engine/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📖 目录

- [产品概述](#-产品概述)
- [核心特性](#-核心特性)
- [快速开始](#-快速开始)
- [安装指南](#-安装指南)
- [配置说明](#-配置说明)
- [API 参考](#-api-参考)
- [自定义与扩展](#-自定义与扩展)
- [交互式 Demo](#-交互式-demo)
- [性能调优与最佳实践](#-性能调优与最佳实践)
- [常见问题](#-常见问题)
- [贡献指南](#-贡献指南)
- [许可证](#-许可证)

---

## 🎯 产品概述

**RecallEngine** 是一款为 AI Agent 设计的“自纠错路由引擎”。它不替代你的 Agent，而是**夹在“用户输入”和“技能执行”中间**：

- 收到输入后，**并行**做两件事：① 意图分类 ② 历史记忆检索；
- 如果分类置信度低，**自动用检索到的历史记忆修正意图**；
- 最终输出确定的技能和参数。

> **核心价值：让 Agent 在“拿不准”的时候，懂得“翻聊天记录”来确认。**

---

## ✨ 核心特性

| 特性 | 说明 |
| :--- | :--- |
| **⚡ 并行化处理** | 路由与记忆检索并行执行，延迟降低 30%~50% |
| **🧠 自适应检索** | 问候、确认、短句自动跳过检索，节省计算资源 |
| **🔄 二次路由** | 低置信度时用记忆修正意图，显著提升准确率 |
| **🧹 质量过滤** | 过滤低分记忆并去重，提升上下文信噪比 |
| **🛡️ 全链路降级** | 任一环节失败不影响整体可用性，保障系统稳定 |
| **🔧 配置热加载** | 支持环境变量动态调整，无需重启服务 |
| **🔌 可插拔架构** | 支持自定义记忆存储（如 ChromaDB）和意图分类器（如 LangChain） |

---

## 🚀 快速开始

### 最简示例（三行代码）

```python
from recall_engine import recall_with_memory

result = recall_with_memory("如何解决 Docker 权限问题？")
print(result["execution_result"])
多轮对话
python
from recall_engine import RecallEngine

engine = RecallEngine()

for query in ["Docker 怎么启动？", "刚才那个命令加上 --restart 参数"]:
    result = engine.route_and_execute(query, session_id="project-123")
    print(f"{query} → {result['skill_name']} ({result['confidence']:.0%})")
返回结果结构
python
{
    "skill_name": "docker_help",       # 最终匹配的技能名
    "confidence": 0.78,                # 最终置信度 (0-1)
    "parameters": {...},               # 提取的参数
    "memory_context": "...",           # 注入的历史记忆文本
    "memory_hits": [...],              # 检索到的原始记忆条目
    "execution_result": "...",         # 技能执行结果
    "archived": False,                 # 是否已归档
    "rerouted": True,                  # 是否触发了二次路由
    "elapsed_ms": 123.4,               # 总耗时（毫秒）
}
📦 安装指南
环境要求
Python 3.8 或更高版本

1. 使用 pip 安装（推荐）
bash
pip install recall-engine
首次安装会自动拉取 jieba 和 scikit-learn 等依赖。

2. 安装可选扩展
命令	说明
pip install recall-engine[demo]	安装交互式 Demo（Streamlit）
pip install recall-engine[dev]	安装开发依赖（pytest、black、flake8）
pip install recall-engine[all]	安装全部可选依赖
3. 从源码安装（开发者）
bash
git clone https://github.com/yourusername/recall-engine.git
cd recall-engine
pip install -e .
4. 验证安装
bash
python -c "from recall_engine import RecallEngine; print('✅ 安装成功')"
常见安装问题
下载速度慢：使用国内镜像 pip install recall-engine -i https://pypi.tuna.tsinghua.edu.cn/simple

权限不足：添加 --user 参数 pip install --user recall-engine

pip 找不到：使用 python -m pip install recall-engine

版本冲突：建议在虚拟环境中安装

⚙️ 配置说明
代码中配置
python
from recall_engine import RecallEngine, RecallEngineConfig

config = RecallEngineConfig(
    memory_dir="./production_memory",          # 记忆存储目录
    min_confidence_threshold=0.35,             # 触发二次路由的阈值
    reroute_boost_threshold=0.20,              # 二次路由需提升的幅度
    parallel_execution=True,                   # 是否并行执行
    enable_adaptive_retrieval=True,            # 是否启用自适应检索
    auto_archive=True,                         # 是否自动归档
    memory_top_k=5,                            # 检索记忆数量
    max_memory_chars=2000,                     # 注入记忆的最大字符数
    memory_min_score=0.25,                     # 记忆最低相关度阈值
)
engine = RecallEngine(config)
环境变量配置（支持热加载）
环境变量	说明	默认值
CONTEXT_MEMORY_DIR	记忆存储目录	./context_memory
CONTEXT_MEMORY_TOP_K	检索记忆数量	3
CONTEXT_MAX_MEMORY_CHARS	记忆最大字符数	2000
CONTEXT_MEMORY_MIN_SCORE	记忆最低相关度	0.25
CONTEXT_MIN_CONFIDENCE	二次路由置信度阈值	0.4
CONTEXT_REROUTE_BOOST	二次路由提升阈值	0.15
CONTEXT_AUTO_ARCHIVE	是否自动归档	true
CONTEXT_PARALLEL	是否并行执行	true
CONTEXT_ADAPTIVE	是否启用自适应检索	true
设置方式（Linux/macOS）：

bash
export CONTEXT_MEMORY_DIR=/data/memory
export CONTEXT_MIN_CONFIDENCE=0.3
引擎会通过 engine.reload_config() 热加载新的环境变量配置。

📚 API 参考
RecallEngine 类
方法	说明
__init__(config, memory_store, classifier)	初始化引擎，支持注入自定义组件
route_and_execute(user_input, session_id, ...)	核心方法：执行完整路由 + 记忆增强 + 执行流程
register_memory_store(store)	运行时替换记忆存储组件
register_classifier(classifier)	运行时替换意图分类器组件
search_memory(query, top_k, session_id)	独立检索记忆（不执行路由）
archive_message(role, text, session_id)	手动归档一条消息
fetch_context(query, max_tokens, session_id)	获取格式化的上下文文本
get_memory_status()	获取记忆系统状态
get_stats()	获取运行统计信息
reload_config()	热加载配置
🧩 自定义与扩展
自定义记忆存储（接入 ChromaDB / Pinecone）
继承 BaseMemoryStore 并实现其 4 个方法：

python
from recall_engine.interfaces import BaseMemoryStore

class MyChromaStore(BaseMemoryStore):
    def search(self, query, top_k, session_id=None):
        # 调用 ChromaDB 检索
        return [{"text": "...", "score": 0.9}]
    def archive(self, role, text, session_id=None):
        # 写入 ChromaDB
        pass
    def fetch_context(self, query, max_tokens, session_id=None):
        # 返回格式化的上下文字符串
        pass
    def get_status(self):
        return {"status": "ok"}

engine = RecallEngine(memory_store=MyChromaStore())
自定义意图分类器（接入 LangChain / HuggingFace）
继承 BaseClassifier 并实现 classify 方法：

python
from recall_engine.interfaces import BaseClassifier

class MyLangChainClassifier(BaseClassifier):
    def classify(self, user_input, context=None):
        # 使用 LangChain 进行意图识别
        # 返回值必须包含 skill_name 和 confidence
        return MyResult(skill_name="...", confidence=0.9, parameters={})

engine = RecallEngine(classifier=MyLangChainClassifier())
🖥️ 交互式 Demo
RecallEngine 提供一个基于 Streamlit 的可视化 Demo，左侧聊天，右侧实时显示决策过程（置信度、记忆命中、二次路由等），是展示产品价值的绝佳工具。

启动 Demo
bash
# 安装 Streamlit（如果尚未安装）
pip install streamlit

# 在项目根目录创建 demo_app.py（内容见下方示例）
streamlit run demo_app.py
浏览器会自动打开 http://localhost:8501。

Demo 截图（示意）
左侧对话区	右侧决策看板
用户输入问题	显示匹配技能、置信度
AI 回复内容	显示记忆命中条目
显示二次路由触发状态
显示完整流程追踪（时间线）
演示剧本（展示“二次路由”）
建记忆：输入 帮我写一个 Nginx 的 Dockerfile

留线索：输入 刚才那个 Dockerfile 加上环境变量

看奇迹：输入 再详细说说

观察右侧面板：记忆命中数增加，二次路由 变为 🔄 已触发，置信度从低变高，完整展示“低置信度 → 检索记忆 → 修正意图”的全过程。

核心实现（demo_app.py 精简版）
python
import streamlit as st
from recall_engine import RecallEngine, RecallEngineConfig

@st.cache_resource
def get_engine():
    config = RecallEngineConfig(memory_dir="./demo_memory", auto_archive=False)
    return RecallEngine(config)

engine = get_engine()
# ... 完整的 UI 代码见 GitHub 示例
🚀 性能调优与最佳实践
场景	建议配置
高频短句（是/否/好）	保持 enable_adaptive_retrieval=True 跳过检索，节省算力
精确技术问答	调高 memory_top_k=5，检索更多历史记录辅助推理
低配服务器（2核4G）	设置 parallel_execution=False，避免线程竞争
记忆库不断增长	调整 archive_max_entries 和 archive_keep_ratio，自动压缩旧记忆
多租户场景	为每个用户/项目分配独立的 session_id，记忆自动隔离
❓ 常见问题
Q1: 需要额外安装向量数据库吗？
不需要。RecallEngine 内置了基于 jieba + scikit-learn 的轻量级文本检索，开箱即用。你也可以接入 ChromaDB 等专用向量库。

Q2: 技能（skills）如何定义？
技能由 intent_classifier 模块加载，你可以将技能定义放在 ./skills/ 目录下（YAML 或 Python 文件），引擎会自动加载。具体格式请参阅 intent_classifier 文档。

Q3: 二次路由什么时候触发？
当意图分类置信度低于 min_confidence_threshold（默认 0.4）且检索到有效记忆时，自动触发二次路由。

Q4: 如何查看引擎内部决策过程？
使用交互式 Demo（Streamlit）即可实时查看每一步。你也可以在 route_and_execute 返回结果中获取 rerouted、confidence、memory_hits 等字段。

Q5: 支持异步调用吗？
当前版本为同步 API，适合大多数 Web 框架。如需异步，可以在 FastAPI 中使用 run_in_executor 包装调用。

Q6: 记忆数据存储在哪里？
默认存储在 ./context_memory 目录下，可以通过 memory_dir 配置修改。

🤝 贡献指南
欢迎贡献代码、提出问题或建议！

Fork 本仓库

创建你的功能分支 (git checkout -b feature/amazing)

提交你的更改 (git commit -m 'Add some amazing feature')

推送到分支 (git push origin feature/amazing)

打开一个 Pull Request

开发环境设置：

bash
pip install -e .[dev]
pytest  # 运行测试
black . # 格式化代码
flake8  # 代码检查
📄 许可证
本项目采用 MIT 许可证，详情请参阅 LICENSE 文件。

🌟 支持
在 GitHub 上给本项目点 ⭐

在 Issues 中报告问题或提出建议

分享给更多 AI 开发者
