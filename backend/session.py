import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


def sanitize_filename(filename: str) -> str:
    """清理文件名中的非法字符"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    # 限制文件名长度
    return filename[:50]


class SessionManager:
    def __init__(self, sessions_dir: Path = None):
        if sessions_dir is None:
            sessions_dir = Path(__file__).parent.parent / "sessions"
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(exist_ok=True)
    
    def _generate_session_file(self, session: Dict[str, Any]) -> Path:
        """生成会话文件路径"""
        created_dt = datetime.fromisoformat(session["created_at"])
        # 格式: YYYYMMDD_HHMMSS_标题
        time_str = created_dt.strftime("%Y%m%d_%H%M%S")
        title_str = sanitize_filename(session["title"])
        safe_title = title_str if title_str else "新对话"
        filename = f"{time_str}_{safe_title}.json"
        return self.sessions_dir / filename
    
    def _find_session_file(self, session_id: str) -> Optional[Path]:
        """根据session_id找到对应的文件"""
        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    session = json.load(f)
                    if session["id"] == session_id:
                        return session_file
            except:
                pass
        return None
    
    def create_session(self, title: str = "新对话") -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now()
        session_data = {
            "id": session_id,
            "title": title,
            "messages": [],
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        self._save_session(session_data)
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session_file = self._find_session_file(session_id)
        if session_file is None:
            return None
        with open(session_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def save_session(self, session_id: str, messages: List[Dict[str, str]]):
        session = self.get_session(session_id)
        if session is None:
            return False
        
        old_file = self._find_session_file(session_id)
        
        session["messages"] = messages
        session["updated_at"] = datetime.now().isoformat()
        
        # 更新标题：如果是新对话，使用第一条消息作为标题
        if session["title"] == "新对话" and messages:
            first_message = messages[0]["content"][:20]
            if len(messages[0]["content"]) > 20:
                first_message += "..."
            session["title"] = first_message
        
        # 删除旧文件（如果标题变了）
        new_file = self._generate_session_file(session)
        if old_file and old_file != new_file:
            old_file.unlink()
        
        self._save_session(session)
        return True
    
    def delete_session(self, session_id: str) -> bool:
        session_file = self._find_session_file(session_id)
        if session_file and session_file.exists():
            session_file.unlink()
            return True
        return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        sessions = []
        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    session = json.load(f)
                    sessions.append({
                        "id": session["id"],
                        "title": session["title"],
                        "created_at": session["created_at"],
                        "updated_at": session["updated_at"]
                    })
            except:
                pass
        # 按更新时间倒序排序
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return sessions
    
    def _save_session(self, session: Dict[str, Any]):
        session_file = self._generate_session_file(session)
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)


# 全局session管理器实例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
