"""
RecallEngine 交互式 Demo — 实时路由过程可视化
"""
import streamlit as st
import sys
import os

# 将当前目录加入系统路径，确保能找到 recall_engine 包
sys.path.insert(0, os.path.dirname(__file__))

from recall_engine import RecallEngine, RecallEngineConfig

# ---------- 初始化引擎（单例） ----------
@st.cache_resource
def _get_engine():
    config = RecallEngineConfig(
        memory_dir="./demo_memory",
        auto_archive=False,
        parallel_execution=True,
        enable_adaptive_retrieval=True,
    )
    return RecallEngine(config)

engine = _get_engine()

st.set_page_config(page_title="RecallEngine Demo", layout="wide")
st.title("🧠 RecallEngine 交互演示")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "process" not in st.session_state:
    st.session_state.process = None

left, right = st.columns([2, 1])

# ========== 左列：聊天 ==========
with left:
    st.subheader("💬 对话")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("输入问题，观察右侧路由过程..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.spinner("⏳ 路由中..."):
            result = engine.route_and_execute(prompt, session_id="demo")

        reply = result.get("execution_result")
        reply_text = (
            reply["error"] if isinstance(reply, dict) and "error" in reply
            else str(reply)[:300] if reply else "（无响应）"
        )

        st.session_state.messages.append({"role": "assistant", "content": reply_text})
        with st.chat_message("assistant"):
            st.write(reply_text)

        st.session_state.process = {
            "input": prompt,
            "skill": result.get("skill_name"),
            "confidence": result.get("confidence", 0),
            "memory_hits": result.get("memory_hits", []),
            "rerouted": result.get("rerouted", False),
            "elapsed_ms": result.get("elapsed_ms", 0),
        }
        st.rerun()

# ========== 右列：决策过程 ==========
with right:
    st.subheader("🔍 决策过程")
    p = st.session_state.process
    if p is None:
        st.info("等待输入...")
    else:
        st.markdown(f"**输入**: {p['input']}")
        st.markdown(f"**技能**: `{p['skill'] or '未匹配'}`")
        st.markdown(f"**置信度**: {p['confidence']:.2f}")
        if p['memory_hits']:
            st.success(f"🧠 记忆命中: {len(p['memory_hits'])} 条")
            with st.expander("记忆详情"):
                for h in p['memory_hits'][:3]:
                    st.caption(f"- {h.get('text','')[:70]}...  (score={h.get('score',0):.2f})")
        else:
            st.info("🧠 记忆命中: 无")
        st.markdown(f"**二次路由**: {'🔄 已触发' if p['rerouted'] else '— 未触发'}")
        st.markdown(f"**耗时**: {p['elapsed_ms']:.1f} ms")
        
        st.divider()
        st.caption("📋 流程追踪")
        steps = ["1. 接收用户输入"]
        if p['memory_hits']:
            steps.append(f"2. 检索记忆 → 命中 {len(p['memory_hits'])} 条")
        else:
            steps.append("2. 检索记忆 → 无结果")
        steps.append(f"3. 意图分类 → {p['skill'] or '未匹配'} (置信度 {p['confidence']:.2f})")
        if p['rerouted']:
            steps.append("4. ⚠️ 低置信度，触发二次路由")
            steps.append("5. ✅ 采纳修正结果")
        else:
            steps.append("4. 置信度达标，跳过二次路由")
        steps.append("6. 执行技能")
        for s in steps:
            st.write(s)

# ========== 侧边栏 ==========
with st.sidebar:
    st.subheader("⚙️ 配置")
    st.caption(f"记忆目录: `{engine.config.memory_dir}`")
    st.caption(f"阈值: {engine.config.min_confidence_threshold}")
    if st.button("🗑️ 重置对话"):
        st.session_state.messages = []
        st.session_state.process = None
        st.rerun()
    st.divider()
    st.caption("💡 试试输入：\n- 'Docker 权限问题'\n- '上次那个问题再详细一下'")