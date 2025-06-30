from swarm import Agent
from src.services.azure_client import AzureOpenAIClient
from src.core.config import Config
from . import get_prompt
import logging

config = Config()
azure_client = AzureOpenAIClient(
    api_key=config.get('azure_openai.api_key'),
    endpoint=config.get('azure_openai.endpoint'),
    api_version=config.get('azure_openai.api_version'),
    deployment_name=config.get('azure_openai.deployment_name')
)
logger = logging.getLogger(__name__)

def internal_monologue(context_variables, current_prompt: str):
    """
    Generate a deep, thoughtful internal monologue using the LLM, reflecting on the current step, doubts, next steps, and possible challenges. Context-aware and similar to Claude Sonnet's style.
    """
    try:
        user_query = context_variables.get('query', '')
        plan = context_variables.get('plan', '')
        monologue_prompt = f"""
You are an advanced AI agent, and this is your internal monologue. Reflect deeply on the current step, your reasoning, doubts, next steps, and possible challenges. Be context-aware, thoughtful, and detailed, similar to Claude Sonnet's style.

User Query:
{user_query}

Current Plan:
{plan}

Current Step or Prompt:
{current_prompt}

Monologue:
"""
        system_prompt = get_prompt('internal_monologue')
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": monologue_prompt}
        ]
        response = azure_client.chat_completion(messages, temperature=0.3)
        monologue = response.choices[0].message.content
        context_variables['internal_monologue'] = monologue
        return monologue
    except Exception as e:
        logger.error(f"Error in internal monologue: {e}")
        monologue = f"(Internal monologue unavailable due to error: {e})"
        context_variables['internal_monologue'] = monologue
        return monologue

internal_monologue_agent = Agent(
    name="Internal Monologue Agent",
    instructions=get_prompt('internal_monologue'),
    functions=[internal_monologue],
) 