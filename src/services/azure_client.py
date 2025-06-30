import yaml
from openai import AzureOpenAI
from typing import Optional
import os
from loguru import logger

PROMPT_FILE = "prompts.yaml"

def load_prompt(key: str) -> str:
    if not os.path.exists(PROMPT_FILE):
        return ""
    with open(PROMPT_FILE, 'r') as f:
        prompts = yaml.safe_load(f)
    return prompts.get(key, "")

class AzureOpenAIClient:
    def __init__(self, api_key: str, endpoint: str, api_version: str, deployment_name: str):
        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
        self.deployment_name = deployment_name
    
    def get_client(self):
        """Return the Azure OpenAI client for use with Swarm"""
        return self.client
    
    def chat_completion(self, messages: list, temperature: float = 0.7, max_tokens: Optional[int] = None):
        """Generate a chat completion using Azure OpenAI"""
        params = {
            "model": self.deployment_name,
            "messages": messages,
            "temperature": temperature
        }
        
        if max_tokens:
            params["max_tokens"] = max_tokens
        
        response = self.client.chat.completions.create(**params)
        return response
    
    def generate_plan(self, query: str, context: str = "") -> str:
        """Generate a research plan for the given query"""
        prompt = load_prompt("planner")
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Query: {query}\n\nContext: {context}\n\nGenerate a step-by-step research plan:"}
        ]
        
        response = self.chat_completion(messages, temperature=0.3)
        return response.choices[0].message.content
    
    def extract_search_queries(self, plan: str) -> list:
        """Extract search queries from a research plan"""
        prompt = load_prompt("extract_search_queries")
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Research plan:\n{plan}\n\nExtract search queries:"}
        ]
        
        response = self.chat_completion(messages, temperature=0.3)
        # Parse the response to extract queries
        content = response.choices[0].message.content
        queries = [line.strip() for line in content.split('\n') if line.strip()]
        return queries
    
    def review_answer(self, query: str, answer: str, sources: list) -> dict:
        """Review and validate an answer"""
        prompt = load_prompt("reviewer")
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Query: {query}\n\nAnswer: {answer}\n\nSources: {sources}\n\nReview:"}
        ]
        
        response = self.chat_completion(messages, temperature=0.2)
        # Parse JSON response
        import json
        try:
            return json.loads(response.choices[0].message.content)
        except:
            return {"approved": False, "score": 0, "feedback": "Failed to parse review response"}
    
    def generate_code(self, requirements: str, context: str = "") -> str:
        """Generate code based on requirements"""
        prompt = load_prompt("coder")
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Requirements: {requirements}\n\nContext: {context}\n\nGenerate code:"}
        ]
        
        response = self.chat_completion(messages, temperature=0.3)
        return response.choices[0].message.content

    def get_completion(self, prompt: str, max_tokens: int = 16384) -> str:
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                stream=True
            )
            result = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    result += chunk.choices[0].delta.content
            return result
        except Exception as e:
            logger.error(f"Azure OpenAI error: {e}")
            # Fallback to non-streaming
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    stream=False
                )
                return response.choices[0].message.content
            except Exception as e2:
                logger.error(f"Azure OpenAI fallback error: {e2}")
                return "" 