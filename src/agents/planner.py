from swarm import Agent
from src.services.azure_client import AzureOpenAIClient
from src.core.config import Config
from . import get_prompt
import logging
import json
import re
from loguru import logger

# Initialize services
config = Config()
azure_client = AzureOpenAIClient(
    api_key=config.get('azure_openai.api_key'),
    endpoint=config.get('azure_openai.endpoint'),
    api_version=config.get('azure_openai.api_version'),
    deployment_name=config.get('azure_openai.deployment_name')
)
logger = logging.getLogger(__name__)

def plan_research(context_variables, query: str):
    """
    Break down the research query into actionable steps, explicitly assigning each step to the correct agent (researcher, coder, etc.).
    Output a clear, step-by-step plan, with each step labeled by agent responsibility.
    """
    try:
        # Get relevant context from knowledge base
        from src.core.knowledge_base import KnowledgeBase
        kb = KnowledgeBase(
            qdrant_url=config.get('qdrant.url', 'http://localhost:6333'),
            collection_name=config.get('qdrant.collection_name', 'research_knowledge')
        )
        context = kb.get_relevant_context(query)

        # Compose LLM prompt for agent-assigned planning
        planning_prompt = f"""
You are a Planner Agent tasked with decomposing a user query into actionable steps for other agents.
The query is: "{query}"
Return a JSON object with the following structure:
{{
    "steps": [
        {{
            "step_number": int,
            "description": str,
            "agent": str,
            "reasoning": str
        }}
    ]
}}
Ensure the response is valid JSON and includes clear, concise steps for agents like Researcher, Coder, Formatter, Runner, and Reporter.
Do not include any text before or after the JSON. Only output the JSON object.
"""
        llm_response = azure_client.generate_plan(planning_prompt, context_variables.get('research_context', ''))
        logger.info(f"Raw LLM response: {llm_response}")
        try:
            plan = json.loads(llm_response)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM plan as JSON: {e}. Attempting to extract JSON.")
            match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if match:
                try:
                    plan = json.loads(match.group(0))
                except Exception as e2:
                    logger.error(f"Could not extract valid JSON. Retrying with fallback plan. {e2}")
                    plan = None
            else:
                plan = None
        if not plan or not isinstance(plan, dict):
            plan = {
                "steps": [
                    {
                        "step_number": 1,
                        "description": f"Research the query: {query}",
                        "agent": "Researcher",
                        "reasoning": "Gather foundational information to address the query."
                    }
                ]
            }
        context_variables['plan'] = plan
        return plan
    except Exception as e:
        logger.error(f"Error in Planner Agent: {e}")
        plan = {
            "steps": [
                {
                    "step_number": 1,
                    "description": f"Research the query: {query}",
                    "agent": "Researcher",
                    "reasoning": "Default to research if planning fails."
                }
            ]
        }
        context_variables['plan'] = plan
        return plan

planner_agent = Agent(
    name="Planner Agent",
    instructions=get_prompt('planner'),
    functions=[plan_research],
) 