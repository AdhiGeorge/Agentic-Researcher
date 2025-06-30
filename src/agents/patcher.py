from swarm import Agent
from . import get_prompt

def patch_code(context_variables, bug_description: str):
    """Debug and fix issues based on user description or error message."""
    # Placeholder: In real use, analyze code and suggest fixes
    context_variables['patch_applied'] = True
    return f"Patched bug: {bug_description}"

def patch_code_agent(context_variables, user_query=None):
    code = context_variables.get('current_code')
    error = context_variables.get('last_error')
    if not code or not error:
        context_variables['patch_output'] = '[ERROR] No code or error to patch.'
        return
    prompt = f"""
You are a Python code fixer. Given the following code and error message, fix the code so it runs without error. If the user has requested a feature or change, implement it as well.

Code:
```python
{code}
```

Error:
{error}

User request (if any):
{user_query or ''}

Return only the fixed code in a Python code block.
"""
    from src.services.azure_client import AzureOpenAIClient
    from src.core.config import Config
    config = Config()
    azure_client = AzureOpenAIClient(
        api_key=config.get('azure_openai.api_key'),
        endpoint=config.get('azure_openai.endpoint'),
        api_version=config.get('azure_openai.api_version'),
        deployment_name=config.get('azure_openai.deployment_name')
    )
    messages = [
        {"role": "system", "content": "You are a helpful Python code fixer."},
        {"role": "user", "content": prompt}
    ]
    response = azure_client.chat_completion(messages, temperature=0.0)
    import re
    code_blocks = re.findall(r'```python(.*?)```', response.choices[0].message.content, re.DOTALL)
    if code_blocks:
        context_variables['current_code'] = code_blocks[-1].strip()
        context_variables['patch_output'] = '[PATCHED CODE]\n' + code_blocks[-1].strip()
        # Track code history
        if 'code_history' not in context_variables:
            context_variables['code_history'] = []
        context_variables['code_history'].append(code_blocks[-1].strip())
    else:
        context_variables['patch_output'] = '[ERROR] No code block returned by LLM.'

patcher_agent = Agent(
    name="Patcher Agent",
    instructions=get_prompt('patcher'),
    functions=[patch_code],
) 