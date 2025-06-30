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

def reason(context_variables, prompt=None):
    user_query = context_variables.get('query', '')
    plan = context_variables.get('plan', '')
    last_output = context_variables.get('output', '')
    debate_mode = context_variables.get('debate', False) or (prompt and 'debate' in prompt.lower())
    if debate_mode:
        # Multi-agent debate: Reasoner, Reviewer, Code Critic
        from src.agents.reviewer import reviewer_agent
        from src.agents.code_critic import code_critic_agent
        # Call reviewer
        review = reviewer_agent.functions[0](context_variables, user_query)
        # Call code critic (dedicated agent)
        code_critique = None
        language = context_variables.get('code_language', 'Python')
        if 'code' in last_output or 'python' in last_output.lower():
            code_critique = code_critic_agent.functions[0](context_variables, language)
        # Reasoner reflection
        reflection = _reason_llm(context_variables, prompt or user_query)
        # Aggregate
        panel = "--- PANEL DEBATE ---\n"
        panel += f"Reasoner: {reflection}\n"
        panel += f"Reviewer: {review}\n"
        if code_critique:
            panel += f"Code Critic: {code_critique}\n"
        panel += "--------------------"
        return panel
    else:
        return _reason_llm(context_variables, prompt or user_query)

def _reason_llm(context_variables, prompt):
    user_query = context_variables.get('query', '')
    plan = context_variables.get('plan', '')
    last_output = context_variables.get('output', '')
    messages = [
        {"role": "system", "content": get_prompt('reasoner')},
        {"role": "user", "content": f"Prompt: {prompt}\n\nQuery: {user_query}\nPlan: {plan}\nLast Output: {last_output}"}
    ]
    try:
        response = azure_client.chat_completion(messages, temperature=0.3)
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Reasoner LLM error: {e}")
        return f"[ERROR] Reasoner LLM failed: {e}"

reasoner_agent = Agent(
    name="Reasoner Agent",
    instructions=get_prompt('reasoner'),
    functions=[reason]
) 