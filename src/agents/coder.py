from swarm import Agent
from src.services.azure_client import AzureOpenAIClient
from src.core.config import Config
from . import get_prompt
import logging
import black
import ast

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
            vix_instructions = ""
            if 'vix' in code_task.lower() or 'vix' in user_query.lower():
                vix_instructions = (
                    "\n\nIMPORTANT: Implement the VIX calculation using the official CBOE formula. "
                    "You must:\n"
                    "- Calculate the forward index level F = K_0 + exp(R*T) * (C(K_0) - P(K_0))\n"
                    "- Use both call and put options\n"
                    "- Compute strike intervals (ΔK)\n"
                    "- Apply the formula: VIX = 100 * sqrt((2/T) * Σ(ΔK_i / K_i^2 * exp(RT) * Q(K_i)) - (1/T) * ((F/K_0) - 1)^2)\n"
                    "- Interpolate for 30-day volatility if multiple expirations are present\n"
                    "- Use realistic sample data\n"
                    "- Include error handling and comments\n"
                    "- Only output valid Python code, no markdown or explanations.\n"
                )
            prompt = (
                (f"Code Feedback (fix these issues): {code_feedback}\n" if code_feedback else "") +
                f"Task: {code_task}{vix_instructions}\n\nResearch Context:\n{formatted_research}\n\nGenerate professional, well-documented code for the above task. Only output valid Python code, no markdown or explanations."
            )
            code = azure_client.generate_code(prompt, formatted_research)
            code = code.replace('```python', '').replace('```', '').strip()
            try:
                code = black.format_str(code, mode=black.FileMode())
            except Exception as e:
                logger.warning(f"Black formatting failed: {e}")
            try:
                ast.parse(code)
            except SyntaxError as e:
                logger.error(f"Syntax error in generated code: {e}")
                cleaned_code = code.replace('\\n', '\n').strip()
                try:
                    ast.parse(cleaned_code)
                    code = cleaned_code
                except SyntaxError:
                    logger.error("Failed to fix syntax error in generated code.")
                    code = f"# Code generation failed due to syntax error: {e}\n# Original code:\n{code}"
            generated_code_blocks.append(code)
        if generated_code_blocks:
            context_variables['generated_code'] = generated_code_blocks[0]  # Only one code block
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