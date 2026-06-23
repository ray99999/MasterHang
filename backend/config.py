import yaml
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

PROVIDERS_INFO = {
    1: {
        "name": "zhipu",
        "full_name": "智谱AI (Zhipu AI)",
        "url": "https://open.bigmodel.cn/"
    },
    2: {
        "name": "qwen",
        "full_name": "阿里通义千问 (Qwen)",
        "url": "https://dashscope.console.aliyun.com/"
    },
    3: {
        "name": "ernie",
        "full_name": "百度文心一言 (ERNIE)",
        "url": "https://cloud.baidu.com/product/wenxinworkshop"
    },
    4: {
        "name": "spark",
        "full_name": "讯飞星火 (Spark)",
        "url": "https://www.xfyun.cn/"
    },
    5: {
        "name": "moonshot",
        "full_name": "月之暗面 (Moonshot)",
        "url": "https://platform.moonshot.cn/"
    },
    6: {
        "name": "doubao",
        "full_name": "字节跳动豆包 (Doubao)",
        "url": "https://www.volcengine.com/"
    },
    7: {
        "name": "deepseek",
        "full_name": "深度求索 (DeepSeek)",
        "url": "https://platform.deepseek.com/"
    },
    8: {
        "name": "volcengine",
        "full_name": "字节跳动火山引擎 (VolcEngine)",
        "url": "https://console.volcengine.com/ark/"
    }
}


def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"配置文件不存在: {CONFIG_PATH}")
    
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    return config


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


def get_provider_info():
    return PROVIDERS_INFO
