import os
import yaml
from dataclasses import dataclass, field
from typing import List, Dict, Any

CONFIG_PATH = os.path.join("config", "config.yaml")

@dataclass
class Snippet:
    name: str
    sql: str

@dataclass
class AIConfig:
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    offline_demo_mode: bool = True
    system_prompt: str = "You are a precise data assistant."
    sql_synth_prompt: str = "You are an expert SQL generator."

@dataclass
class DataConfig:
    file_path: str = "data/sample_sales.csv"
    table_name: str = "sales"
    additional_details: str = ""

@dataclass
class AppConfig:
    ai: AIConfig = field(default_factory=AIConfig)
    data: DataConfig = field(default_factory=DataConfig)
    snippets: List[Snippet] = field(default_factory=list)

def load_config() -> AppConfig:
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        save_config(AppConfig())  # write defaults
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    ai = AIConfig(**raw.get("ai", {}))
    data = DataConfig(**raw.get("data", {}))
    snippets = [Snippet(**s) for s in raw.get("snippets", [])]
    return AppConfig(ai=ai, data=data, snippets=snippets)

def save_config(cfg: AppConfig):
    raw = {
        "ai": {
            "provider": cfg.ai.provider,
            "model": cfg.ai.model,
            "temperature": cfg.ai.temperature,
            "offline_demo_mode": cfg.ai.offline_demo_mode,
            "system_prompt": cfg.ai.system_prompt,
            "sql_synth_prompt": cfg.ai.sql_synth_prompt,
        },
        "data": {
            "file_path": cfg.data.file_path,
            "table_name": cfg.data.table_name,
            "additional_details": cfg.data.additional_details,
        },
        "snippets": [ {"name": s.name, "sql": s.sql} for s in cfg.snippets ],
    }
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, sort_keys=False, allow_unicode=True)
