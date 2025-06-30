# Agent modules 
import yaml
import os

PROMPTS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'prompts.yaml')

_prompts_cache = None

def get_prompt(key):
    global _prompts_cache
    if _prompts_cache is None:
        with open(PROMPTS_PATH, 'r', encoding='utf-8') as f:
            _prompts_cache = yaml.safe_load(f)
    return _prompts_cache.get(key, '') 