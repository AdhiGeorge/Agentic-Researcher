from swarm import Agent
from . import get_prompt
from src.services.azure_client import AzureOpenAIClient
from src.core.config import Config
import logging

config = Config()
azure_client = AzureOpenAIClient(
    api_key=config.get('azure_openai.api_key'),
    endpoint=config.get('azure_openai.endpoint'),
    api_version=config.get('azure_openai.api_version'),
    deployment_name=config.get('azure_openai.deployment_name')
)
logger = logging.getLogger(__name__)

def code_critic(context_variables, language='Python'):
    code = context_variables.get('current_code') or context_variables.get('code') or ''
    if not code:
        logger.warning('[CodeCritic] No code found in context.')
        return '[ERROR] No code found to review.'
    prompt = get_prompt('code_critic')
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Review this {language} code for bugs, style, and best practices. Give a detailed critique.\n\nCode:\n{code}"}
    ]
    try:
        response = azure_client.chat_completion(messages, temperature=0.2)
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f'[CodeCritic] LLM error: {e}')
        return f'[ERROR] Code Critic LLM failed: {e}'

code_critic_agent = Agent(
    name='Code Critic Agent',
    instructions=get_prompt('code_critic'),
    functions=[code_critic],
) 