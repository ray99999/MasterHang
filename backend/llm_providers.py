import httpx
import json
from typing import List, Dict, Any, AsyncGenerator
from backend.config import load_config, get_provider_info


class BaseProvider:
    async def chat(self, messages: List[Dict[str, Any]], stream: bool = False):
        raise NotImplementedError
    
    async def get_models(self) -> List[str]:
        raise NotImplementedError
    
    def _process_messages_for_multimodal(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """处理消息以支持多模态输入"""
        processed = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            attachments = msg.get("attachments", [])
            
            if not attachments:
                # 没有附件，保持原样
                processed.append({"role": role, "content": content})
            else:
                # 有附件，构建多模态内容
                parts = []
                if content:
                    parts.append({"type": "text", "text": content})
                
                for att in attachments:
                    if att.get("type", "").startswith("image/") and att.get("data"):
                        # 添加图片
                        parts.append({
                            "type": "image_url",
                            "image_url": {"url": att["data"]}
                        })
                
                processed.append({"role": role, "content": parts})
        
        return processed


class ZhipuProvider(BaseProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        self.models_url = "https://open.bigmodel.cn/api/paas/v4/models"
    
    async def chat(self, messages: List[Dict[str, Any]], stream: bool = False):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        processed_messages = self._process_messages_for_multimodal(messages)
        data = {
            "model": self.model,
            "messages": processed_messages,
            "stream": stream
        }
        
        if stream:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", self.base_url, headers=headers, json=data) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            line = line[6:]
                            if line == "[DONE]":
                                break
                            try:
                                chunk = json.loads(line)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except:
                                pass
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.base_url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                yield result["choices"][0]["message"]["content"]
    
    async def get_models(self) -> List[str]:
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.models_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                models = []
                for m in data.get("data", []):
                    if m.get("object") == "model" or m.get("type") == "model":
                        models.append(m["id"])
                return models
        except:
            return ["glm-4-flash", "glm-4", "glm-4-plus", "glm-3-turbo"]


class QwenProvider(BaseProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        self.models_url = "https://dashscope.aliyuncs.com/api/v1/models"
    
    async def chat(self, messages: List[Dict[str, str]], stream: bool = False):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "input": {
                "messages": messages
            },
            "parameters": {
                "result_format": "message"
            }
        }
        
        if stream:
            data["parameters"]["incremental_output"] = True
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", self.base_url, headers=headers, json=data) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            line = line[6:]
                            try:
                                chunk = json.loads(line)
                                if "output" in chunk and "choices" in chunk["output"]:
                                    delta = chunk["output"]["choices"][0].get("message", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except:
                                pass
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.base_url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                yield result["output"]["choices"][0]["message"]["content"]
    
    async def get_models(self) -> List[str]:
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.models_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                models = []
                for m in data.get("data", []):
                    if m.get("object") == "model" or m.get("type") == "model":
                        models.append(m["id"])
                return models
        except:
            return ["qwen-turbo", "qwen-plus", "qwen-max", "qwen-max-longcontext"]


class ErnieProvider(BaseProvider):
    def __init__(self, api_key: str, secret_key: str, model: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.model = model
        self.base_url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{model}"
    
    async def _get_access_token(self):
        url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={self.api_key}&client_secret={self.secret_key}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url)
            response.raise_for_status()
            return response.json()["access_token"]
    
    async def chat(self, messages: List[Dict[str, str]], stream: bool = False):
        access_token = await self._get_access_token()
        url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{self.model}?access_token={access_token}"
        headers = {"Content-Type": "application/json"}
        data = {
            "messages": messages,
            "stream": stream
        }
        
        if stream:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", url, headers=headers, json=data) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            line = line[6:]
                            try:
                                chunk = json.loads(line)
                                content = chunk.get("result", "")
                                if content:
                                    yield content
                            except:
                                pass
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                yield result["result"]
    
    async def get_models(self) -> List[str]:
        return ["ernie-3.5-turbo", "ernie-3.5-turbo-128k", "ernie-4.0", "ernie-4.0-turbo"]


class MoonshotProvider(BaseProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.moonshot.cn/v1/chat/completions"
        self.models_url = "https://api.moonshot.cn/v1/models"
    
    async def chat(self, messages: List[Dict[str, Any]], stream: bool = False):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        processed_messages = self._process_messages_for_multimodal(messages)
        data = {
            "model": self.model,
            "messages": processed_messages,
            "stream": stream
        }
        
        if stream:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", self.base_url, headers=headers, json=data) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            line = line[6:]
                            if line == "[DONE]":
                                break
                            try:
                                chunk = json.loads(line)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except:
                                pass
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.base_url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                yield result["choices"][0]["message"]["content"]
    
    async def get_models(self) -> List[str]:
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.models_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                models = []
                for m in data.get("data", []):
                    if m.get("object") == "model" or m.get("type") == "model":
                        models.append(m["id"])
                return models
        except:
            return ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]


class DoubaoProvider(BaseProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        self.models_url = "https://ark.cn-beijing.volces.com/api/v3/models"
    
    async def chat(self, messages: List[Dict[str, Any]], stream: bool = False):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        processed_messages = self._process_messages_for_multimodal(messages)
        data = {
            "model": self.model,
            "messages": processed_messages,
            "stream": stream
        }
        
        if stream:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", self.base_url, headers=headers, json=data) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            line = line[6:]
                            if line == "[DONE]":
                                break
                            try:
                                chunk = json.loads(line)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except:
                                pass
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.base_url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                yield result["choices"][0]["message"]["content"]
    
    async def get_models(self) -> List[str]:
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.models_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                models = []
                for m in data.get("data", []):
                    if m.get("object") == "model" or m.get("type") == "model":
                        models.append(m["id"])
                return models
        except:
            return ["doubao-pro-4k", "doubao-pro-32k", "doubao-lite-4k"]


class DeepSeekProvider(BaseProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.deepseek.com/chat/completions"
        self.models_url = "https://api.deepseek.com/models"
    
    async def chat(self, messages: List[Dict[str, Any]], stream: bool = False):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        processed_messages = self._process_messages_for_multimodal(messages)
        data = {
            "model": self.model,
            "messages": processed_messages,
            "stream": stream
        }
        
        if stream:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", self.base_url, headers=headers, json=data) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            line = line[6:]
                            if line == "[DONE]":
                                break
                            try:
                                chunk = json.loads(line)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except:
                                pass
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.base_url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                yield result["choices"][0]["message"]["content"]
    
    async def get_models(self) -> List[str]:
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                print(f"正在调用 DeepSeek 模型列表 API: {self.models_url}")
                response = await client.get(self.models_url, headers=headers)
                print(f"响应状态码: {response.status_code}")
                response.raise_for_status()
                data = response.json()
                print(f"响应数据: {data}")
                models = []
                for m in data.get("data", []):
                    # DeepSeek 用的是 object 字段而不是 type 字段
                    if m.get("object") == "model" or m.get("type") == "model":
                        models.append(m["id"])
                return models
        except Exception as e:
            print(f"获取 DeepSeek 模型列表异常: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return ["deepseek-chat", "deepseek-coder"]


class VolcEngineProvider(BaseProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions"
        self.models_url = "https://ark.cn-beijing.volces.com/api/coding/v3/models"
    
    async def chat(self, messages: List[Dict[str, Any]], stream: bool = False):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        processed_messages = self._process_messages_for_multimodal(messages)
        data = {
            "model": self.model,
            "messages": processed_messages,
            "stream": stream
        }
        
        if stream:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", self.base_url, headers=headers, json=data) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            line = line[6:]
                            if line == "[DONE]":
                                break
                            try:
                                chunk = json.loads(line)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except:
                                pass
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.base_url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                yield result["choices"][0]["message"]["content"]
    
    async def get_models(self) -> List[str]:
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.models_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                models = []
                for m in data.get("data", []):
                    if m.get("object") == "model" or m.get("type") == "model":
                        models.append(m["id"])
                # 火山引擎可能需要自定义模型ID，提供一些常见的模型
                if not models:
                    models = ["doubao-pro-4k", "doubao-pro-32k", "doubao-lite-4k", "doubao-lite-32k"]
                return models
        except Exception as e:
            print(f"获取火山引擎模型列表异常: {str(e)}")
            # 提供默认模型列表
            return ["doubao-pro-4k", "doubao-pro-32k", "doubao-lite-4k", "doubao-lite-32k"]


def get_provider_by_config(provider_config: Dict[str, Any]) -> BaseProvider:
    provider_name = provider_config["name"]
    
    if provider_name == "zhipu":
        return ZhipuProvider(provider_config["api_key"], provider_config["model"])
    elif provider_name == "qwen":
        return QwenProvider(provider_config["api_key"], provider_config["model"])
    elif provider_name == "ernie":
        return ErnieProvider(provider_config["api_key"], provider_config["secret_key"], provider_config["model"])
    elif provider_name == "moonshot":
        return MoonshotProvider(provider_config["api_key"], provider_config["model"])
    elif provider_name == "doubao":
        return DoubaoProvider(provider_config["api_key"], provider_config["model"])
    elif provider_name == "deepseek":
        return DeepSeekProvider(provider_config["api_key"], provider_config["model"])
    elif provider_name == "volcengine":
        return VolcEngineProvider(provider_config["api_key"], provider_config["model"])
    else:
        raise ValueError(f"不支持的模型厂商: {provider_name}")


def get_provider():
    config = load_config()
    selected_provider_id = config["selected_provider"]
    # 兼容字符串和整数键
    provider_config = config["providers"].get(selected_provider_id) or config["providers"].get(str(selected_provider_id))
    if not provider_config:
        raise ValueError(f"未找到厂商配置: {selected_provider_id}")
    return get_provider_by_config(provider_config)
