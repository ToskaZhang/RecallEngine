"""
RecallEngine - 记忆增强型意图路由与执行引擎 v2.0

特性：
  - ⚡ 并行化：路由与记忆检索并行执行
  - 🧠 自适应检索：问候/短句自动跳过
  - 🔄 二次路由：低置信度时用记忆修正
  - 🛡️ 全链路降级：任一环节失败不影响整体
  - 🔌 可插拔架构：支持自定义存储/分类器
"""

from __future__ import annotations
import os
import json
import time
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from .interfaces import BaseMemoryStore, BaseClassifier
from .defaults import ArchiverMemoryStore, IntentClassifierWrapper, SkillCall


@dataclass
class RecallEngineConfig:
    """配置类，支持环境变量动态加载"""

    # 记忆系统
    memory_dir: str = "./context_memory"
    default_session_id: str = "default"
    memory_top_k: int = 3
    max_memory_chars: int = 2000
    memory_min_score: float = 0.25

    # 路由系统
    min_confidence_threshold: float = 0.4
    reroute_boost_threshold: float = 0.15

    # 行为控制
    auto_archive: bool = True
    parallel_execution: bool = True
    enable_adaptive_retrieval: bool = True

    # 内部参数
    archive_max_entries: int = 5000
    archive_keep_ratio: float = 0.7
    archive_retrain_interval: int = 50

    @classmethod
    def from_env(cls) -> "RecallEngineConfig":
        return cls(
            memory_dir=os.getenv("CONTEXT_MEMORY_DIR", "./context_memory"),
            default_session_id=os.getenv("CONTEXT_SESSION_ID", "default"),
            memory_top_k=int(os.getenv("CONTEXT_MEMORY_TOP_K", "3")),
            max_memory_chars=int(os.getenv("CONTEXT_MAX_MEMORY_CHARS", "2000")),
            memory_min_score=float(os.getenv("CONTEXT_MEMORY_MIN_SCORE", "0.25")),
            min_confidence_threshold=float(os.getenv("CONTEXT_MIN_CONFIDENCE", "0.4")),
            reroute_boost_threshold=float(os.getenv("CONTEXT_REROUTE_BOOST", "0.15")),
            auto_archive=os.getenv("CONTEXT_AUTO_ARCHIVE", "true").lower() == "true",
            parallel_execution=os.getenv("CONTEXT_PARALLEL", "true").lower() == "true",
            enable_adaptive_retrieval=os.getenv("CONTEXT_ADAPTIVE", "true").lower()
            == "true",
        )

    def reload(self) -> "RecallEngineConfig":
        new = RecallEngineConfig.from_env()
        for k, v in new.__dict__.items():
            setattr(self, k, v)
        return self


class RecallEngine:
    """记忆增强型意图路由与执行引擎"""

    def __init__(
        self,
        config: Optional[RecallEngineConfig] = None,
        memory_store: Optional[BaseMemoryStore] = None,
        classifier: Optional[BaseClassifier] = None,
    ):
        self.config = config or RecallEngineConfig.from_env()
        self._memory_store = memory_store or ArchiverMemoryStore(self.config)
        self._classifier = classifier or IntentClassifierWrapper()

        # 预检查技能执行函数是否可用
        try:
            from intent_classifier import execute_skill

            self._execute_skill = execute_skill
        except ImportError:
            self._execute_skill = None

        self._session_id = self.config.default_session_id
        self._conversation_history: List[Dict[str, str]] = []
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._stats = {
            "total_calls": 0,
            "memory_hits_avg": 0.0,
            "reroute_count": 0,
            "fallback_count": 0,
        }

    def register_memory_store(self, store: BaseMemoryStore) -> None:
        self._memory_store = store

    def register_classifier(self, classifier: BaseClassifier) -> None:
        self._classifier = classifier

    def route_and_execute(
        self,
        user_input: str,
        session_id: Optional[str] = None,
        inject_memory: bool = True,
        auto_archive: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """完整的路由 + 记忆增强 + 执行流程"""
        start_time = time.perf_counter()
        sid = session_id or self._session_id
        auto_archive = (
            auto_archive if auto_archive is not None else self.config.auto_archive
        )
        self._stats["total_calls"] += 1

        # 1. 预判是否需要检索
        need_retrieval = self._need_memory_retrieval(user_input)
        if not inject_memory or not need_retrieval:
            need_retrieval = False

        # 2. 并行执行
        route_result = None
        memory_hits = []
        if self.config.parallel_execution and need_retrieval:
            route_future = self._executor.submit(self._safe_route, user_input)
            search_future = self._executor.submit(
                self._safe_search, user_input, sid, self.config.memory_top_k
            )
            route_result = route_future.result()
            memory_hits = search_future.result() or []
        else:
            route_result = self._safe_route(user_input)
            if need_retrieval:
                memory_hits = (
                    self._safe_search(user_input, sid, self.config.memory_top_k) or []
                )

        if route_result is None:
            return self._build_error("未匹配到任何技能", start_time)

        # 3. 解包
        skill_name = getattr(route_result, "skill_name", None) or getattr(
            route_result, "name", None
        )
        confidence = getattr(route_result, "confidence", 0.0)
        parameters = (
            getattr(route_result, "parameters", {}).copy()
            if hasattr(route_result, "parameters")
            else {}
        )

        if not skill_name:
            return self._build_error("路由结果无效", start_time)

        # 4. 过滤记忆
        if memory_hits:
            memory_hits = self._filter_memory_hits(
                memory_hits, self.config.memory_min_score
            )

        memory_context = ""
        if memory_hits:
            memory_context = self._truncate_text(
                self._format_memory_context(memory_hits), self.config.max_memory_chars
            )

        # 5. 二次路由
        rerouted = False
        if memory_context and confidence < self.config.min_confidence_threshold:
            new_result = self._reroute_with_memory(
                user_input, route_result, memory_context
            )
            if new_result is not None:
                new_conf = getattr(new_result, "confidence", 0.0)
                if new_conf > confidence + self.config.reroute_boost_threshold:
                    route_result = new_result
                    skill_name = getattr(route_result, "skill_name", skill_name)
                    confidence = new_conf
                    parameters = (
                        getattr(route_result, "parameters", {}).copy() or parameters
                    )
                    rerouted = True
                    self._stats["reroute_count"] += 1

        # 6. 注入记忆
        if memory_context:
            parameters["_memory_context"] = memory_context
            parameters["_memory_hits"] = memory_hits
        if rerouted:
            parameters["_rerouted"] = True
        if confidence < self.config.min_confidence_threshold:
            parameters["_low_confidence"] = True

        # 7. 执行
        enhanced_call = self._to_skill_call(route_result, parameters)
        execution_result = self._safe_execute(enhanced_call, skill_name)
        if isinstance(execution_result, dict) and "error" in execution_result:
            self._stats["fallback_count"] += 1

        # 8. 归档
        archived = False
        if auto_archive:
            archived = self._safe_archive(user_input, execution_result, sid)

        self._conversation_history.append({"role": "user", "content": user_input})
        if isinstance(execution_result, str):
            self._conversation_history.append(
                {"role": "assistant", "content": execution_result[:500]}
            )

        self._stats["memory_hits_avg"] = (
            self._stats["memory_hits_avg"] * 0.9 + len(memory_hits) * 0.1
        )

        return {
            "skill_name": skill_name,
            "confidence": confidence,
            "parameters": parameters,
            "memory_context": memory_context,
            "memory_hits": memory_hits,
            "execution_result": execution_result,
            "archived": archived,
            "rerouted": rerouted,
            "elapsed_ms": (time.perf_counter() - start_time) * 1000,
        }

    # ---------- 独立记忆操作 ----------
    def search_memory(
        self, query: str, top_k: Optional[int] = None, session_id: Optional[str] = None
    ) -> List[Dict]:
        return self._safe_search(query, session_id or self._session_id, top_k) or []

    def archive_message(
        self, role: str, text: str, session_id: Optional[str] = None
    ) -> bool:
        return self._memory_store.archive(role, text, session_id or self._session_id)

    def fetch_context(
        self, query: str, max_tokens: int = 500, session_id: Optional[str] = None
    ) -> str:
        try:
            return self._memory_store.fetch_context(
                query, max_tokens, session_id or self._session_id
            )
        except Exception:
            return ""

    def get_memory_status(self) -> Dict:
        try:
            return self._memory_store.get_status()
        except Exception:
            return {"error": "无法获取记忆状态"}

    def get_stats(self) -> Dict:
        return {**self._stats, "conversation_length": len(self._conversation_history)}

    def reload_config(self) -> None:
        self.config.reload()

    # ---------- 内部方法 ----------
    def _need_memory_retrieval(self, user_input: str) -> bool:
        if not self.config.enable_adaptive_retrieval:
            return True
        stripped = user_input.strip()
        skip = {
            "你好",
            "嗨",
            "hello",
            "hi",
            "谢谢",
            "感谢",
            "thanks",
            "是",
            "否",
            "对",
            "不",
            "继续",
            "开始",
            "结束",
            "停",
            "好",
            "ok",
            "好的",
            "嗯",
        }
        if stripped in skip:
            return False
        if len(stripped) < 3:
            return False
        if stripped.isdigit() or all(not c.isalnum() for c in stripped):
            return False
        return True

    def _filter_memory_hits(self, hits: List[Dict], min_score: float) -> List[Dict]:
        filtered = [h for h in hits if h.get("score", 0) >= min_score]
        seen = {}
        for h in filtered:
            text = h.get("text", "")
            if text and (
                text not in seen or h.get("score", 0) > seen[text].get("score", 0)
            ):
                seen[text] = h
        return sorted(seen.values(), key=lambda x: x.get("score", 0), reverse=True)

    def _format_memory_context(self, hits: List[Dict]) -> str:
        if not hits:
            return ""
        lines = ["【相关历史记忆】"]
        for i, h in enumerate(hits, 1):
            ts = (
                datetime.fromtimestamp(h.get("timestamp", 0)).strftime("%H:%M")
                if h.get("timestamp")
                else ""
            )
            lines.append(
                f"{i}. [{h.get('role', '?')}] {h.get('text', '')} (相关度: {h.get('score', 0):.2f}{', ' + ts if ts else ''})"
            )
        return "\n".join(lines)

    def _truncate_text(self, text: str, max_chars: int) -> str:
        return text[:max_chars] + "...(已截断)" if len(text) > max_chars else text

    def _reroute_with_memory(
        self, user_input: str, original_result, memory_context: str
    ):
        try:
            enhanced = f"{user_input}\n[历史上下文]: {memory_context[:300]}"
            new_result = self._classifier.classify(enhanced)
            if new_result is None:
                return None
            new_conf = getattr(new_result, "confidence", 0.0)
            orig_conf = getattr(original_result, "confidence", 0.0)
            return (
                new_result
                if new_conf > orig_conf + self.config.reroute_boost_threshold
                else None
            )
        except Exception:
            return None

    def _to_skill_call(self, route_result, parameters: Dict) -> Any:
        if hasattr(route_result, "execution_type") and hasattr(
            route_result, "execution_target"
        ):
            if SkillCall:
                return SkillCall(
                    skill_name=getattr(route_result, "skill_name", ""),
                    confidence=getattr(route_result, "confidence", 0.0),
                    parameters=parameters,
                    execution_type=getattr(route_result, "execution_type", "prompt"),
                    execution_target=getattr(route_result, "execution_target", ""),
                    raw_reason=getattr(route_result, "raw_reason", ""),
                )
        if isinstance(route_result, dict):
            if SkillCall:
                return SkillCall(
                    skill_name=route_result.get("skill_name", ""),
                    confidence=route_result.get("confidence", 0.0),
                    parameters=parameters,
                    execution_type=route_result.get("execution_type", "prompt"),
                    execution_target=route_result.get("execution_target", ""),
                    raw_reason=route_result.get("raw_reason", ""),
                )
        return route_result

    def _safe_route(self, user_input: str):
        try:
            return self._classifier.classify(user_input)
        except Exception:
            return None

    def _safe_search(
        self, query: str, session_id: str, top_k: Optional[int] = None
    ) -> List[Dict]:
        try:
            k = top_k or self.config.memory_top_k
            return self._memory_store.search(query, top_k=k, session_id=session_id)
        except Exception:
            return []

    def _safe_execute(self, call, skill_name: str) -> Union[str, Dict]:
        if self._execute_skill is None:
            return {
                "error": "执行器不可用，请安装 intent_classifier",
                "skill": skill_name,
            }
        try:
            result = self._execute_skill(call)
            return result
        except Exception as e:
            return {"error": f"技能执行失败: {e}", "skill": skill_name}

    def _safe_archive(self, user_input: str, execution_result, session_id: str) -> bool:
        try:
            self._memory_store.archive("user", user_input, session_id)
            if isinstance(execution_result, str):
                self._memory_store.archive(
                    "assistant", execution_result[:500], session_id
                )
            elif isinstance(execution_result, dict) and "error" not in execution_result:
                self._memory_store.archive(
                    "assistant", json.dumps(execution_result)[:500], session_id
                )
            return True
        except Exception:
            return False

    def _build_error(self, msg: str, start_time: float) -> Dict:
        return {
            "skill_name": None,
            "confidence": 0.0,
            "parameters": {},
            "memory_context": "",
            "memory_hits": [],
            "execution_result": {"error": msg},
            "archived": False,
            "rerouted": False,
            "elapsed_ms": (time.perf_counter() - start_time) * 1000,
        }

    def __del__(self):
        if hasattr(self, "_executor"):
            self._executor.shutdown(wait=False)


# ---------- 全局单例 ----------
_global_engine: Optional[RecallEngine] = None


def get_engine(config: Optional[RecallEngineConfig] = None) -> RecallEngine:
    global _global_engine
    if _global_engine is None:
        _global_engine = RecallEngine(config)
    return _global_engine


def recall_with_memory(
    user_input: str, session_id: Optional[str] = None, **kwargs
) -> Dict[str, Any]:
    """快捷函数：带记忆增强的路由 + 执行"""
    return get_engine().route_and_execute(user_input, session_id=session_id, **kwargs)


def reload_engine_config() -> None:
    get_engine().reload_config()


if __name__ == "__main__":
    os.makedirs("./test_memory", exist_ok=True)
    config = RecallEngineConfig(memory_dir="./test_memory", parallel_execution=True)
    engine = RecallEngine(config)

    print("=" * 60)
    print("🚀 RecallEngine v2.0 演示")
    print("=" * 60)

    for q in ["Docker 权限问题", "上次那个问题", "你好", "详细说一下"]:
        result = engine.route_and_execute(q)
        print(f"\n输入: {q}")
        print(f"  技能: {result['skill_name']} | 置信度: {result['confidence']:.0%}")
        print(
            f"  记忆: {len(result['memory_hits'])}条 | 耗时: {result['elapsed_ms']:.1f}ms"
        )

    print(f"\n📊 统计: {engine.get_stats()}")
