from swarm import Agent
from src.services.azure_client import AzureOpenAIClient
from src.core.config import Config
from . import get_prompt
import logging

# Initialize services
config = Config()
azure_client = AzureOpenAIClient(
    api_key=config.get('azure_openai.api_key'),
    endpoint=config.get('azure_openai.endpoint'),
    api_version=config.get('azure_openai.api_version'),
    deployment_name=config.get('azure_openai.deployment_name')
)

logger = logging.getLogger(__name__)

def generate_code(context_variables):
    """
    Only process the code-related steps from the plan. For each step assigned to the Coder, generate code based on the research context and plan. If 'chain_of_thought' is enabled, include explicit step-by-step reasoning and intermediate thoughts. Log all reasoning steps.
    """
    try:
        plan = context_variables.get('plan', [])
        code_steps = [step for step in plan if isinstance(step, dict) and step.get('agent', '').lower() == 'coder']
        user_query = context_variables.get('query', '')
        formatted_research = context_variables.get('formatted_research', '')
        code_feedback = context_variables.get('code_feedback', '')
        generated_code_blocks = []
        chain_of_thought = context_variables.get('chain_of_thought', False)
        for step in code_steps:
            code_task = step.get('task', '')
            if not code_task:
                continue
            if chain_of_thought:
                cot_prompt = (
                    (f"Code Feedback (fix these issues): {code_feedback}\n" if code_feedback else "") +
                    f"Task: {code_task}\n\nResearch Context:\n{formatted_research}\n\nGenerate professional, well-documented code for the above task. Think step by step, show your intermediate reasoning, and explain your thought process before giving the final code."
                )
                logger.info(f"[Chain-of-Thought] Code step: {code_task}")
                code = azure_client.generate_code(cot_prompt, formatted_research)
            else:
                prompt = (
                    (f"Code Feedback (fix these issues): {code_feedback}\n" if code_feedback else "") +
                    f"Task: {code_task}\n\nResearch Context:\n{formatted_research}\n\nGenerate professional, well-documented code for the above task."
                )
                code = azure_client.generate_code(prompt, formatted_research)
            generated_code_blocks.append(code)
        if generated_code_blocks:
            context_variables['generated_code'] = '\n\n'.join(generated_code_blocks)
        else:
            context_variables['generated_code'] = ''
        return context_variables['generated_code']
    except Exception as e:
        logger.error(f"Error in coder: {e}")
        context_variables['generated_code'] = f"(Code unavailable due to error: {e})"
        return context_variables['generated_code']

coder_agent = Agent(
    name="Coder Agent",
    instructions=get_prompt('coder'),
    functions=[generate_code],
) 