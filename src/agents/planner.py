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

def plan_research(context_variables, query: str):
    """
    Break down the research query into actionable steps, explicitly assigning each step to the correct agent (researcher, coder, etc.).
    Output a clear, step-by-step plan, with each step labeled by agent responsibility.
    """
    try:
        # Get relevant context from knowledge base
        from src.core.knowledge_base import KnowledgeBase
        kb = KnowledgeBase(
            host=config.get('qdrant.host'),
            port=config.get('qdrant.port'),
            collection_name=config.get('qdrant.collection_name')
        )
        context = kb.get_relevant_context(query)

        # Compose LLM prompt for agent-assigned planning
        planning_prompt = f"""
You are an expert AI project planner. Given the following user query, break it down into a step-by-step plan. For each step, explicitly assign the responsible agent (choose from: Researcher, Coder, Formatter, Answer, Runner, Reporter, Patcher, InternalMonologue). For each step, provide:
- agent: The responsible agent
- task: The specific task or sub-question
- reasoning: Why this step is needed and why this agent is best for it

Also provide a summary and focus area for the overall plan.

**IMPORTANT:**
- Always return a valid JSON list of steps, plus a summary and focus_area field at the end.
- Never return plain text, markdown, or any other format.
- If you are unsure, output an empty JSON list.

User Query:
{query}

Relevant Context:
{context}

Format your response as a JSON list of steps, each with 'agent', 'task', and 'reasoning', plus a 'summary' and 'focus_area' field at the end.
"""
        llm_response = azure_client.generate_plan(planning_prompt, context)
        # Try to parse the LLM response as JSON
        import json
        import re
        try:
            plan_struct = json.loads(llm_response)
        except Exception as e:
            logger.warning(f"Failed to parse LLM plan as JSON: {e}. Attempting to extract JSON from output.")
            # Try to extract JSON from the LLM output using regex
            json_match = re.search(r'(\[.*?\]|\{.*?\})', llm_response, re.DOTALL)
            if json_match:
                try:
                    plan_struct = json.loads(json_match.group(0))
                except Exception as e2:
                    logger.warning(f"Failed to extract JSON from LLM output: {e2}. Falling back to raw text.")
                    plan_struct = llm_response
            else:
                plan_struct = llm_response

        # Extract search queries for the researcher
        search_queries = []
        if isinstance(plan_struct, list):
            for step in plan_struct:
                if isinstance(step, dict) and step.get('agent', '').lower() == 'researcher':
                    search_queries.append(step.get('task', ''))
        else:
            # Fallback: try to extract lines for researcher
            import re
            search_queries = re.findall(r'Researcher.*?: (.*)', str(plan_struct))

        # Update context variables
        context_variables['plan'] = plan_struct
        context_variables['search_queries'] = search_queries
        context_variables['research_context'] = context
        context_variables['plan_summary'] = plan_struct.get('summary', '') if isinstance(plan_struct, dict) else ''
        context_variables['plan_focus_area'] = plan_struct.get('focus_area', '') if isinstance(plan_struct, dict) else ''

        # Log the interaction
        if 'session_id' in context_variables:
            from src.core.database import Database
            db = Database(config.get('database.path'))
            db.log_agent_interaction(
                session_id=context_variables['session_id'],
                agent_name="Planner",
                action="generate_plan",
                result=str(plan_struct)
            )

        # Hand off to researcher
        from .researcher import researcher_agent
        return researcher_agent

    except Exception as e:
        logger.error(f"Error in planner: {e}")
        # Fallback to simple plan
        context_variables['plan'] = [
            {"agent": "Researcher", "task": f"Research: {query}", "reasoning": "Default to research if planning fails."}
        ]
        context_variables['search_queries'] = [query]
        from .researcher import researcher_agent
        return researcher_agent

planner_agent = Agent(
    name="Planner Agent",
    instructions=get_prompt('planner'),
    functions=[plan_research],
) 