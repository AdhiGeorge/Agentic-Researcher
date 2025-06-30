from swarm import Agent
from . import get_prompt
from src.services.azure_client import AzureOpenAIClient
from src.core.config import Config
import logging
from src.agents import runner, patcher, reporter

config = Config()
azure_client = AzureOpenAIClient(
    api_key=config.get('azure_openai.api_key'),
    endpoint=config.get('azure_openai.endpoint'),
    api_version=config.get('azure_openai.api_version'),
    deployment_name=config.get('azure_openai.deployment_name')
)
logger = logging.getLogger(__name__)

def determine_action(context_variables, user_message: str):
    """
    Use the LLM to classify the user's intent from their natural language command and route to the correct agent.
    Supports: run code, fix code, add feature, export, show research, show code, etc.
    """
    try:
        # Compose a prompt for intent classification
        prompt = f"""
You are an intent classifier for an agentic research system. Given the user's message, classify the intent as one of:
- run_code: Run the current code
- fix_code: Fix errors in the code
- add_feature: Add a new feature to the code (describe the feature)
- export: Export the research/code/output (specify format if given)
- show_research: Show the research output
- show_code: Show the code
- show_sources: Show the sources
- undo: Undo the last code change
- show_code_history: Show all previous code versions
- answer: Answer a follow-up or clarify
- other: Anything else

User message: {user_message}

Respond with only the intent label (e.g., 'run_code', 'fix_code', etc.), and if 'add_feature' or 'export', include a short description after a colon (e.g., 'add_feature: plot the VIX').
"""
        messages = [
            {"role": "system", "content": "You are an intent classifier for an agentic research system."},
            {"role": "user", "content": prompt}
        ]
        response = azure_client.chat_completion(messages, temperature=0.0)
        intent_line = response.choices[0].message.content.strip().split('\n')[0].lower()
        if ':' in intent_line:
            intent, detail = intent_line.split(':', 1)
            intent = intent.strip()
            detail = detail.strip()
        else:
            intent = intent_line.strip()
            detail = ''
        context_variables['action_intent'] = intent
        context_variables['action_detail'] = detail
        # Route to agent
        if intent == 'run_code':
            # Call the runner agent's run_code function
            runner.run_code(context_variables)
            return 'run_code'
        elif intent == 'fix_code':
            patcher.patch_code_agent(context_variables)
            return 'fix_code'
        elif intent == 'add_feature':
            # Pass only the feature detail to patch_code_agent
            patcher.patch_code_agent(context_variables, detail)
            return 'add_feature'
        elif intent == 'export':
            # Call the reporter agent's generate_report function
            reporter.generate_report(context_variables)
            return 'export'
        elif intent == 'show_code':
            context_variables['run_output'] = context_variables.get('current_code', '[No code found]')
            return 'show_code'
        elif intent == 'show_research':
            context_variables['run_output'] = context_variables.get('research_results', '[No research found]')
            return 'show_research'
        elif intent == 'show_sources':
            from .reviewer import reviewer_agent
            return reviewer_agent
        elif intent == 'undo':
            # Undo last code change
            history = context_variables.get('code_history', [])
            if history and len(history) > 1:
                history.pop()  # Remove current
                context_variables['current_code'] = history[-1]
                context_variables['run_output'] = '[UNDO] Reverted to previous code version.'
            else:
                context_variables['run_output'] = '[UNDO] No previous code version to revert to.'
            return 'undo'
        elif intent == 'show_code_history':
            history = context_variables.get('code_history', [])
            if history:
                code_versions = '\n\n'.join([f'--- Version {i+1} ---\n{code}' for i, code in enumerate(history)])
                context_variables['run_output'] = code_versions
            else:
                context_variables['run_output'] = '[No code history found]'
            return 'show_code_history'
        else:
            from .answer import answer_agent
            return answer_agent
    except Exception as e:
        logger.error(f"Error in intent classification: {e}")
        from .answer import answer_agent
        return answer_agent

action_agent = Agent(
    name="Action Agent",
    instructions=get_prompt('action'),
    functions=[determine_action],
) 