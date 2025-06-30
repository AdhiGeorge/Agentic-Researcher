from src.agents.planner import planner_agent
from src.agents.researcher import researcher_agent
from src.agents.reviewer import reviewer_agent
from src.agents.coder import coder_agent
from src.agents.runner import runner_agent
from src.agents.formatter import formatter_agent
from src.agents.action import action_agent
from src.agents.feature import feature_agent
from src.agents.patcher import patcher_agent
from src.agents.reporter import reporter_agent
from src.agents.internal_monologue import internal_monologue_agent
from src.agents.answer import answer_agent
from src.agents.reasoner import reasoner_agent
from src.agents.code_critic import code_critic_agent

AGENTS = {
    'planner': planner_agent,
    'researcher': researcher_agent,
    'reviewer': reviewer_agent,
    'coder': coder_agent,
    'runner': runner_agent,
    'formatter': formatter_agent,
    'action': action_agent,
    'feature': feature_agent,
    'patcher': patcher_agent,
    'reporter': reporter_agent,
    'internal_monologue': internal_monologue_agent,
    'answer': answer_agent,
    'reasoner': reasoner_agent,
    'code_critic': code_critic_agent,
    # 'mother': MotherAgent(),  # Removed to break circular import
} 