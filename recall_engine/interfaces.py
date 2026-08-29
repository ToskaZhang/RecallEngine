"""RecallEngine Interfaces — 抽象接口定义"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any


class BaseMemoryStore(ABC):
    """记忆存储抽象接口"""

    @abstractmethod
    def search(
        self, query: str, top_k: int, session_id: Optional[str] = None
    ) -> List[Dict]:
        """检索与 query 相关的记忆条目，返回含 text 和 score 的列表"""
        pass

    @abstractmethod
    def archive(self, role: str, text: str, session_id: Optional[str] = None) -> bool:
        """存储一条对话记录"""
        pass

    @abstractmethod
    def fetch_context(
        self, query: str, max_tokens: int, session_id: Optional[str] = None
    ) -> str:
        """获取格式化的上下文文本"""
        pass

    @abstractmethod
    def get_status(self) -> Dict:
        """返回存储系统的状态信息"""
        pass


class BaseClassifier(ABC):
    """意图分类器抽象接口"""

    @abstractmethod
    def classify(self, user_input: str, context: Optional[str] = None) -> Any:
        """
        对用户输入进行分类

        Returns:
            应包含 skill_name (str), confidence (float), parameters (dict)
        """
        pass
