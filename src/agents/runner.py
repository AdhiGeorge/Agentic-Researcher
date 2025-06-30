from swarm import Agent
import threading
import tempfile
import subprocess
import os
from src.core.config import Config
from . import get_prompt
import logging
import re

# Initialize services
config = Config()
logger = logging.getLogger(__name__)

def extract_python_code_from_context(context_variables):
    """
    Search all relevant fields in the context for Python code blocks and return the last one found.
    """
    # 1. Check for direct 'current_code' (for backward compatibility)
    if context_variables.get('current_code'):
        return context_variables['current_code']
    # 2. Search in all 'output' fields that look like research/answer sections
    code_blocks = []
    for key, value in context_variables.items():
        if isinstance(value, str):
            # Try to extract code blocks from string
            code_blocks += re.findall(r'```python\s*(.*?)```', value, re.DOTALL)
        elif isinstance(value, dict):
            for v in value.values():
                if isinstance(v, str):
                    code_blocks += re.findall(r'```python\s*(.*?)```', v, re.DOTALL)
    # 3. Search in session history (list of dicts)
    if isinstance(context_variables.get('history'), list):
        for entry in context_variables['history']:
            for v in entry.values():
                if isinstance(v, str):
                    code_blocks += re.findall(r'```python\s*(.*?)```', v, re.DOTALL)
    # 4. Search in session file structure (list of dicts, as in the session JSON)
    if isinstance(context_variables.get('session'), list):
        for entry in context_variables['session']:
            for v in entry.values():
                if isinstance(v, str):
                    code_blocks += re.findall(r'```python\s*(.*?)```', v, re.DOTALL)
    # 5. If still nothing, try to parse nested JSON in 'output' fields
    for key, value in context_variables.items():
        if isinstance(value, str) and value.strip().startswith('{'):
            try:
                import json
                obj = json.loads(value)
                for v in obj.values():
                    if isinstance(v, str):
                        code_blocks += re.findall(r'```python\s*(.*?)```', v, re.DOTALL)
            except Exception:
                pass
    return code_blocks[-1] if code_blocks else None

def run_code(context_variables):
    """Execute the generated code in a separate thread and return the output."""
    try:
        code = extract_python_code_from_context(context_variables)
        if not code:
            context_variables['run_output'] = '[ERROR] No code found to execute.'
            return
        context_variables['current_code'] = code  # Always update for downstream agents
        
        output = {}
        
        def exec_code():
            try:
                # Create temporary file
                with tempfile.NamedTemporaryFile('w', delete=False, suffix='.py') as f:
                    f.write(code)
                    temp_path = f.name
                
                # Execute the code
                result = subprocess.run(
                    ['python', temp_path], 
                    capture_output=True, 
                    text=True, 
                    timeout=30
                )
                
                output['stdout'] = result.stdout.strip()
                output['stderr'] = result.stderr.strip()
                output['return_code'] = result.returncode
                
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
            except subprocess.TimeoutExpired:
                output['stderr'] = "Code execution timed out after 30 seconds"
                output['return_code'] = -1
            except Exception as e:
                output['stderr'] = str(e)
                output['return_code'] = -1
        
        # Execute in separate thread
        thread = threading.Thread(target=exec_code)
        thread.start()
        thread.join()
        
        # Update context variables
        context_variables['run_output'] = output
        context_variables['execution_successful'] = output.get('return_code', -1) == 0
        context_variables['last_error'] = output.get('stderr', '')
        
        # Log the interaction
        if 'session_id' in context_variables:
            from src.core.database import Database
            db = Database(config.get('database.path'))
            db.log_code_execution(
                session_id=context_variables['session_id'],
                code=code,
                output=output.get('stdout', ''),
                error=output.get('stderr', '')
            )
            db.log_agent_interaction(
                session_id=context_variables['session_id'],
                agent_name="Runner",
                action="execute_code",
                result=f"Success: {context_variables['execution_successful']}, Output: {len(output.get('stdout', ''))} chars"
            )
        
        # Format output for user display
        if output.get('return_code', -1) == 0:
            formatted = f"[bold green]✓ CODE EXECUTED SUCCESSFULLY[/bold green]\n[bold]Output:[/bold]\n{output.get('stdout', 'No output')}"
        else:
            formatted = f"[bold red]✗ CODE EXECUTION FAILED[/bold red]\n[bold]Error:[/bold]\n{output.get('stderr', 'Unknown error')}"
        context_variables['run_output'] = formatted
        
        # Hand off back to reviewer for final review
        from .reviewer import reviewer_agent
        return reviewer_agent
        
    except Exception as e:
        logger.error(f"Error in runner: {e}")
        context_variables['run_output'] = f'[EXCEPTION] {str(e)}'
        context_variables['execution_successful'] = False
        context_variables['last_error'] = str(e)
        return f"Code execution failed: {str(e)}"

runner_agent = Agent(
    name="Runner Agent",
    instructions=get_prompt('runner'),
    functions=[run_code],
) 