"""RecallEngine Defaults — 默认适配器实现"""
from __future__ import annotations
from typing import List, Dict, Optional, Any
import os
import sys
from .interfaces import BaseMemoryStore, BaseClassifier


def _import_with_fallback(module_name: str, fallback_paths: List[str], attrs: List[str]):
    """从多个候选路径导入模块并获取指定属性"""
    original_path = sys.path[:]
    for path in fallback_paths:
        if not path:
            continue
        if os.path.isdir(path):
            sys.path.insert(0, path)
        try:
            mod = __import__(module_name, fromlist=attrs)
            result = tuple(getattr(mod, attr) for attr in attrs)
            return result
        except (ImportError, AttributeError):
            sys.path = original_path[:]
            continue
        finally:
            sys.path = original_path[:]
    return (None,) * len(attrs)


_possible_archiver_paths = [
    os.environ.get('CONTEXT_ARCHIVER_PATH', ''),
    os.path.join(os.path.dirname(__file__), '..', 'skills', 'context-archiver'),
    './context_archiver',
]
ContextArchiver, ArchiverConfig = _import_with_fallback(
    'context_archiver', _possible_archiver_paths, ['ContextArchiver', 'ArchiverConfig']
)

_possible_classifier_paths = [
    os.environ.get('INTENT_CLASSIFIER_PATH', ''),
    os.path.join(os.path.dirname(__file__), '..', 'plugins', 'superpowers'),
    './intent_classifier',
]
route_task, SkillCall = _import_with_fallback(
    'intent_classifier', _possible_classifier_paths, ['route_task', 'SkillCall']
)


class ArchiverMemoryStore(BaseMemoryStore):
    """基于 context_archiver 的默认记忆存储"""

    def __init__(self, config):
        if ContextArchiver is None:
            raise ImportError("❌ 未找到 context_archiver")
        self.archiver = ContextArchiver(ArchiverConfig(
            memory_dir=config.memory_dir,
            max_entries_before_compress=config.archive_max_entries,
            compress_keep_ratio=config.archive_keep_ratio,
            retrain_interval=config.archive_retrain_interval,
        ))
        os.makedirs(config.memory_dir, exist_ok=True)

    def search(self, query: str, top_k: int, session_id: Optional[str] = None) -> List[Dict]:
        return self.archiver.search(query, top_k=top_k, session_id=session_id)

    def archive(self, role: str, text: str, session_id: Optional[str] = None) -> bool:
        try:
            self.archiver.archive(role, text, session_id=session_id)
            return True
        except Exception:
            return False

    def fetch_context(self, query: str, max_tokens: int, session_id: Optional[str] = None) -> str:
        return self.archiver.fetch_relevant(query, max_tokens=max_tokens, session_id=session_id)

    def get_status(self) -> Dict:
        return self.archiver.get_status()


class IntentClassifierWrapper(BaseClassifier):
    """基于 intent_classifier 的默认分类器"""

    def __init__(self, skills_dir: Optional[str] = None):
        if route_task is None:
            raise ImportError("❌ 未找到 intent_classifier")
        self.skills_dir = skills_dir or os.environ.get("SKILLS_DIR", "./skills")

    def classify(self, user_input: str, context: Optional[str] = None) -> Any:
        enhanced_input = f"{user_input}\n[上下文]: {context[:300]}" if context else user_input
        return route_task(enhanced_input)