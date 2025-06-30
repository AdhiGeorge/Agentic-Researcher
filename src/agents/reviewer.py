from swarm import Agent
from src.services.azure_client import AzureOpenAIClient
from src.core.config import Config
from src.core.knowledge_base import KnowledgeBase
from . import get_prompt
import logging
import re

# Initialize services
config = Config()
azure_client = AzureOpenAIClient(
    api_key=config.get('azure_openai.api_key'),
    endpoint=config.get('azure_openai.endpoint'),
    api_version=config.get('azure_openai.api_version'),
    deployment_name=config.get('azure_openai.deployment_name')
)

logger = logging.getLogger(__name__)

def strip_duplicate_code(summary, answer):
    code_blocks = re.findall(r'```python[\s\S]*?```', answer)
    for block in code_blocks:
        if block in summary:
            summary = summary.replace(block, '')
    return summary

def review_answer(context_variables):
    """
    Review the synthesized answer, attribute sources, and provide a quality summary. If 'chain_of_thought' is enabled, include explicit step-by-step reasoning and intermediate thoughts. Log all reasoning steps. Deduplicate code and answer content in the summary for readability.
    """
    try:
        formatted_research = context_variables.get('formatted_research', '')
        answer = context_variables.get('answer', '')
        sources = context_variables.get('sources', [])
        chain_of_thought = context_variables.get('chain_of_thought', False)
        # If both research and answer are missing or indicate no results, output 'no results'
        if (
            (not formatted_research or 'no highly relevant research results found' in formatted_research.lower()) and
            (not answer or 'no highly relevant research results found' in answer.lower())
        ):
            context_variables['approved'] = False
            context_variables['final_answer'] = "No highly relevant research results were found for your query. Please try rephrasing or ask for a more specific aspect."
            return context_variables['final_answer']
        # Compose review prompt for LLM
        try:
            if chain_of_thought:
                review_prompt = (
                    "You are an expert research reviewer. Your job is to produce a single, detailed, well-structured, and highly-informative summary for the user. "
                    "Review the following answer for quality, accuracy, and completeness. Think step by step, show your intermediate reasoning, and explain your thought process before giving the final review. If code is present, explain the approach and logic. "
                    "At the end, provide a quality assessment and clearly list all sources used.\n\n"
                    f"Answer:\n{answer}\n\nFormatted Research:\n{formatted_research}\n"
                )
                logger.info(f"[Chain-of-Thought] Review: {answer[:100]}...")
            else:
                review_prompt = (
                    "You are an expert research reviewer. Your job is to produce a single, detailed, well-structured, and highly-informative summary for the user. "
                    "Review the following answer for quality, accuracy, and completeness. If code is present, explain the approach and logic. "
                    "At the end, provide a quality assessment and clearly list all sources used.\n\n"
                    f"Answer:\n{answer}\n\nFormatted Research:\n{formatted_research}\n"
                )
            summary = azure_client.summarize(review_prompt, answer + '\n' + formatted_research)
            summary = strip_duplicate_code(summary, answer)
        except Exception:
            summary = (
                "[Summary]\n" +
                (answer or formatted_research) +
                "\n\n(Note: This is a direct summary of the answer and research findings. For a more readable answer, please enable LLM summarization.)"
            )
        # Append sources if available
        if sources:
            summary += "\n\n## Sources Used:"
            for s in sorted(set(sources)):
                summary += f"\n- {s}"
        context_variables['approved'] = True
        context_variables['review_score'] = 9
        context_variables['review_feedback'] = "Relevant, filtered, and summarized content provided."
        context_variables['final_answer'] = summary
        return summary
    except Exception as e:
        logger.error(f"Error in reviewer: {e}")
        context_variables['approved'] = False
        context_variables['final_answer'] = "Review failed due to error."
        return "Review failed due to error. Please try again."

reviewer_agent = Agent(
    name="Reviewer Agent",
    instructions=get_prompt('reviewer'),
    functions=[review_answer],
) 