from loguru import logger
import json

class InteractionAgent:
    def __init__(self, agents: dict, knowledge_base, azure_client):
        self.agents = agents  # Dictionary of agent instances (e.g., {'runner': ..., 'coder': ...})
        self.knowledge_base = knowledge_base
        self.azure_client = azure_client

    def handle_follow_up(self, command: str, session_id: str) -> dict:
        """
        Interpret the follow-up command and route to the appropriate agent.
        Supported commands: 'run the code', 'explain', 'fix the code', etc.
        Returns a JSON response with the action taken and result.
        """
        try:
            prompt = f"""
Interpret the follow-up command: '{command}'
Based on the session ID {session_id}, determine the appropriate action:
- If 'run the code', execute the stored code using the Runner Agent.
- If 'explain', retrieve relevant information from the knowledge base and explain.
- If 'fix the code', identify errors and regenerate using the Coder Agent.
- For other commands, provide a natural-language response or route to appropriate agents.
Return a JSON response with the action taken and result.
"""
            response = self.azure_client.get_completion(prompt)
            action = json.loads(response)
            if action.get("action") == "run_code":
                code = self.knowledge_base.retrieve_code(session_id)
                return self.agents["runner"].run_code(code)
            elif action.get("action") == "explain":
                report = self.knowledge_base.retrieve_report(session_id)
                return {"status": "success", "output": report}
            elif action.get("action") == "fix_code":
                error = action.get("error", "")
                research_data = self.knowledge_base.retrieve_research(session_id=session_id)
                new_code = self.agents["coder"].generate_code(action.get("query", ""), research_data, error)
                return self.agents["runner"].run_code(new_code)
            else:
                return {"status": "success", "output": action.get("response", "Command handled.")}
        except Exception as e:
            logger.error(f"Error handling follow-up: {e}")
            return {"status": "error", "error": str(e)} 