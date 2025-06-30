from swarm import Agent
from src.services.azure_client import AzureOpenAIClient
from src.core.config import Config
from src.core.knowledge_base import KnowledgeBase
from . import get_prompt
import logging
import re

config = Config()
azure_client = AzureOpenAIClient(
    api_key=config.get('azure_openai.api_key'),
    endpoint=config.get('azure_openai.endpoint'),
    api_version=config.get('azure_openai.api_version'),
    deployment_name=config.get('azure_openai.deployment_name')
)
logger = logging.getLogger(__name__)

kb = KnowledgeBase(
    host=config.get('qdrant.host'),
    port=config.get('qdrant.port'),
    collection_name=config.get('qdrant.collection_name')
)

def get_non_code_text_length(markdown_text):
    # Find the first code block
    code_block_match = re.search(r'```[\w+]*\n', markdown_text)
    if code_block_match:
        return len(markdown_text[:code_block_match.start()])
    return len(markdown_text)

def chunk_text(text, max_chars=10000):
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

def summarize_chunk(chunk, user_query, system_prompt, rag_context):
    prompt = (
        "You are an expert research assistant. Summarize the following research chunk in a highly detailed, exhaustive, and well-structured manner. Include all relevant facts, explanations, and context. Do not include code.\n\n"
        f"User Query:\n{user_query}\n\nResearch Chunk:\n{chunk}\n\nKnowledge Base Context:\n{rag_context}\n\nSummary:"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    response = azure_client.chat_completion(messages, temperature=0.3)
    return response.choices[0].message.content

def is_llm_refusal(text):
    refusal_phrases = [
        "i'm sorry",
        "constraints of this platform",
        "unable to generate",
        "cannot fulfill this request",
        "exceeds the character limit",
        "let me know how you'd like to proceed"
    ]
    return any(phrase in text.lower() for phrase in refusal_phrases)

def synthesize_section(section_title, section_prompt, context, user_query, system_prompt, rag_context):
    prompt = f"""
You are an expert AI assistant. Write the section '{section_title}' for a research report. {section_prompt}

User Query:
{user_query}

Research Context:
{context}

Knowledge Base Context:
{rag_context}

Section: {section_title}
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    for _ in range(3):
        response = azure_client.chat_completion(messages, temperature=0.3)
        section = response.choices[0].message.content
        if not is_llm_refusal(section):
            return section
        # Retry with a softer prompt
        messages[-1]["content"] = prompt + "\n\nPlease provide as much detail as possible, but do not worry about length limits."
    return f"(Section unavailable due to LLM refusal)"

def generate_answer(context_variables, user_query: str):
    """
    Synthesize each answer section separately to avoid LLM refusals, then combine. If 'chain_of_thought' is enabled, include explicit step-by-step reasoning and intermediate thoughts for each section. Log all reasoning steps.
    """
    try:
        formatted_research = context_variables.get('formatted_research', '')
        session_id = context_variables.get('session_id', None)
        rag_context = ''
        if context_variables.get('is_followup', False):
            rag_context = kb.get_relevant_context(user_query, limit=3)
        system_prompt = get_prompt('answer')
        sections = [
            ("Introduction", "Explain what the VIX is, its purpose, and how it reflects market volatility."),
            ("Theory/Background", "Describe how the VIX is calculated, what implied volatility is, weighted average, time to expiration, etc."),
            ("Mathematical Formula", "Provide the VIX formula in LaTeX, and explain each variable in a bullet list."),
            ("Step-by-Step Calculation", "Enumerate the steps to calculate the VIX, e.g., collect data, calculate F, determine ΔK, compute weighted values, aggregate, apply formula."),
            ("Python Code", "Provide a full, well-documented Python implementation in a code block, following the user's style."),
            ("Usage Example", "Show how to use the code with sample data."),
            ("Sources", "List all sources as bullet points.")
        ]
        answer_parts = []
        chain_of_thought = context_variables.get('chain_of_thought', False)
        for section_title, section_prompt in sections:
            if chain_of_thought:
                cot_prompt = f"{section_prompt}\n\nFor this section, think step by step, show your intermediate reasoning, and explain your thought process before giving the final answer."
                section_text = synthesize_section(
                    section_title,
                    cot_prompt,
                    formatted_research,
                    user_query,
                    system_prompt,
                    rag_context
                )
                logger.info(f"[Chain-of-Thought] {section_title}: {section_text}")
            else:
                section_text = synthesize_section(
                    section_title,
                    section_prompt,
                    formatted_research,
                    user_query,
                    system_prompt,
                    rag_context
                )
            answer_parts.append(f"## {section_title}\n\n{section_text}\n")
        answer = "# Volatility Index (VIX): Explanation, Formula, and Python Code\n\n" + "\n".join(answer_parts)
        context_variables['answer'] = answer
        if len(answer) > 10000:
            chunk_size = 10000
            answer_chunks = [answer[i:i+chunk_size] for i in range(0, len(answer), chunk_size)]
            context_variables['answer_chunks'] = answer_chunks
            return answer
        # Extract the latest Python code block for execution
        code_blocks = re.findall(r'```python(.*?)```', answer, re.DOTALL)
        if code_blocks:
            context_variables['current_code'] = code_blocks[-1].strip()
            # Track code history
            if 'code_history' not in context_variables:
                context_variables['code_history'] = []
            context_variables['code_history'].append(code_blocks[-1].strip())
        else:
            # Try to extract from the 'output' of the last 'Python Code' section if present
            python_code_section = re.findall(r'## Python Code\s+```python(.*?)```', answer, re.DOTALL)
            if python_code_section:
                context_variables['current_code'] = python_code_section[-1].strip()
                if 'code_history' not in context_variables:
                    context_variables['code_history'] = []
                context_variables['code_history'].append(python_code_section[-1].strip())
            else:
                logger.warning('No Python code block found in answer for execution.')
        return answer
    except Exception as e:
        logger.error(f"Error in answer agent: {e}")
        answer = f"(Answer unavailable due to error: {e})"
        context_variables['answer'] = answer
        return answer

answer_agent = Agent(
    name="Answer Agent",
    instructions=get_prompt('answer'),
    functions=[generate_answer],
) 