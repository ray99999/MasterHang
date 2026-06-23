from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
from pathlib import Path
from backend.config import load_config, save_config, get_provider_info
from backend.llm_providers import get_provider, get_provider_by_config
from backend.session import get_session_manager

app = FastAPI()

frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

images_path = Path(__file__).parent.parent / "images"
app.mount("/images", StaticFiles(directory=images_path), name="images")


class Attachment(BaseModel):
    name: str
    type: str
    data: str
    preview: Optional[str] = None


class Message(BaseModel):
    role: str
    content: str
    attachments: Optional[List[Attachment]] = None


class ChatRequest(BaseModel):
    messages: List[Message]
    stream: bool = True


class ConfigUpdate(BaseModel):
    selected_provider: int
    providers: Dict[str, Any]


class VerifyPasswordRequest(BaseModel):
    password: str


class UpdatePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class AgentSettings(BaseModel):
    personality: str
    age: str
    selfName: str
    callUser: str
    description: str


# 配置文件路径
agent_settings_path = Path(__file__).parent.parent / "agent_settings.json"
knowledge_dir = Path(__file__).parent.parent / "knowledge"

# 确保knowledge目录存在
knowledge_dir.mkdir(exist_ok=True)


@app.post("/api/verify-password")
async def verify_password(request: VerifyPasswordRequest):
    try:
        config = load_config()
        if config.get("admin_password", "admin") == request.password:
            return {"success": True}
        return {"success": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/update-password")
async def update_password(request: UpdatePasswordRequest):
    try:
        config = load_config()
        if config.get("admin_password", "admin") != request.old_password:
            return {"success": False, "message": "原密码错误"}
        config["admin_password"] = request.new_password
        save_config(config)
        return {"success": True, "message": "密码更新成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def read_root():
    return FileResponse(frontend_path / "index.html")


@app.get("/api/config")
async def get_config():
    try:
        config = load_config()
        provider_info = get_provider_info()
        return {
            "success": True,
            "config": config,
            "providers_info": provider_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config")
async def update_config(config_update: ConfigUpdate):
    try:
        config = load_config()
        config["selected_provider"] = config_update.selected_provider
        # 转换 providers 的键从字符串转回整数
        config["providers"] = {
            int(k): v for k, v in config_update.providers.items()
        }
        save_config(config)
        return {"success": True, "message": "配置已更新"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ModelsRequest(BaseModel):
    provider_id: int


@app.post("/api/models")
async def get_models(request: ModelsRequest):
    try:
        config = load_config()
        # 确保能正确获取 provider_config（兼容字符串和整数键）
        provider_config = config["providers"].get(request.provider_id) or config["providers"].get(str(request.provider_id))
        if not provider_config:
            raise ValueError(f"未找到厂商配置: {request.provider_id}")
        provider = get_provider_by_config(provider_config)
        models = await provider.get_models()
        return {
            "success": True,
            "models": models
        }
    except Exception as e:
        import traceback
        print(f"获取模型列表失败: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


def load_agent_settings():
    if agent_settings_path.exists():
        with open(agent_settings_path, "r", encoding="utf-8") as f:
            import json
            return json.load(f)
    return {
        "personality": "",
        "age": "",
        "selfName": "",
        "callUser": "",
        "description": ""
    }


def save_agent_settings(settings: dict):
    import json
    with open(agent_settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


@app.get("/api/agent-settings")
async def get_agent_settings():
    try:
        settings = load_agent_settings()
        return {
            "success": True,
            "settings": settings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent-settings")
async def update_agent_settings(settings: AgentSettings):
    try:
        save_agent_settings(settings.dict())
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/knowledge-files")
async def get_knowledge_files():
    try:
        files = []
        if knowledge_dir.exists():
            for file in knowledge_dir.iterdir():
                if file.is_file() and file.suffix.lower() == ".txt":
                    files.append(file.name)
        return {
            "success": True,
            "files": files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def build_system_prompt() -> str:
    """构建智能体系统prompt"""
    settings = load_agent_settings()
    parts = []
    
    has_settings = False
    
    # 身份设定部分
    identity_parts = []
    if settings.get("description"):
        identity_parts.append(settings['description'])
    if settings.get("personality"):
        identity_parts.append(f"性格特点：{settings['personality']}")
    if settings.get("age"):
        identity_parts.append(f"设定年龄：{settings['age']}")
    if settings.get("selfName"):
        identity_parts.append(f"对自己的称呼：{settings['selfName']}")
    if settings.get("callUser"):
        identity_parts.append(f"对用户的称呼：{settings['callUser']}")
    
    if identity_parts:
        parts.append("【角色设定】")
        parts.extend(identity_parts)
        has_settings = True
    
    # 知识库部分
    knowledge_content = []
    if knowledge_dir.exists():
        for file in knowledge_dir.iterdir():
            if file.is_file() and file.suffix.lower() == ".txt":
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        content = f.read()
                        if content.strip():
                            knowledge_content.append(f"【{file.name}】\n{content}")
                except Exception:
                    pass
    
    if knowledge_content:
        if has_settings:
            parts.append("")
        parts.append("【参考知识】")
        parts.extend(knowledge_content)
    
    if parts:
        return "\n".join(parts)
    return ""


class SessionChatRequest(BaseModel):
    session_id: Optional[str] = None
    messages: List[Message]
    stream: bool = True


@app.get("/api/sessions")
async def list_sessions():
    try:
        session_manager = get_session_manager()
        sessions = session_manager.list_sessions()
        return {
            "success": True,
            "sessions": sessions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    try:
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        return {
            "success": True,
            "session": session
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions")
async def create_session():
    try:
        session_manager = get_session_manager()
        session_id = session_manager.create_session()
        return {
            "success": True,
            "session_id": session_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    try:
        session_manager = get_session_manager()
        session_manager.delete_session(session_id)
        return {
            "success": True,
            "message": "会话已删除"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        provider = get_provider()
        # 构建包含附件的消息
        messages = []
        for msg in request.messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.attachments:
                msg_dict["attachments"] = [
                    att.model_dump() for att in msg.attachments
                ]
            messages.append(msg_dict)
        
        # 添加系统prompt
        system_prompt = build_system_prompt()
        if system_prompt:
            messages.insert(0, {"role": "system", "content": system_prompt})
        
        if request.stream:
            async def generate():
                async for chunk in provider.chat(messages, stream=True):
                    yield chunk
            
            return StreamingResponse(generate(), media_type="text/plain")
        else:
            response = ""
            async for chunk in provider.chat(messages, stream=False):
                response += chunk
            return {"success": True, "response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions/chat")
async def session_chat(request: SessionChatRequest):
    try:
        session_manager = get_session_manager()
        provider = get_provider()
        
        # 构建包含附件的消息
        messages = []
        for msg in request.messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.attachments:
                msg_dict["attachments"] = [
                    att.model_dump() for att in msg.attachments
                ]
            messages.append(msg_dict)
        
        # 获取或创建会话
        session_id = request.session_id
        if session_id is None:
            session_id = session_manager.create_session()
        
        # 保存用户消息（不包含系统prompt）
        session_manager.save_session(session_id, messages)
        
        # 构建发送给模型的消息（包含系统prompt）
        messages_with_system = list(messages)
        system_prompt = build_system_prompt()
        if system_prompt:
            messages_with_system.insert(0, {"role": "system", "content": system_prompt})
        
        # 生成回复
        full_response = ""
        if request.stream:
            async def generate():
                nonlocal full_response
                async for chunk in provider.chat(messages_with_system, stream=True):
                    full_response += chunk
                    yield chunk
            
            async def stream_with_save():
                async for chunk in generate():
                    yield chunk
                # 保存完整对话
                messages.append({"role": "assistant", "content": full_response})
                session_manager.save_session(session_id, messages)
            
            return StreamingResponse(stream_with_save(), media_type="text/plain")
        else:
            async for chunk in provider.chat(messages_with_system, stream=False):
                full_response += chunk
            # 保存完整对话
            messages.append({"role": "assistant", "content": full_response})
            session_manager.save_session(session_id, messages)
            return {"success": True, "response": full_response, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
