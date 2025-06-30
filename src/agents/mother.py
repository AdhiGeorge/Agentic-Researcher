# from src.core.agent_registry import AGENTS  # Remove this import

class MotherAgent:
    """
    The orchestrator for Agentres. Controls the workflow, dynamic handoffs, and overall agentic process.
    """
    def __init__(self):
        from src.core.agent_registry import AGENTS  # Import here to avoid circular import
        self.agents = AGENTS

    def run(self, user_query: str, context_variables: dict = None):
        if context_variables is None:
            context_variables = {}
        context_variables['query'] = user_query
        context_variables['is_followup'] = context_variables.get('is_followup', False)
        messages = [{"role": "user", "content": user_query}]
        history = []

        # Detect export request in user query
        export_formats = ['pdf', 'txt', 'docx']
        export_format = None
        for fmt in export_formats:
            if fmt in user_query.lower():
                export_format = fmt
                break
        if export_format:
            context_variables['export_format'] = export_format
            context_variables['export_path'] = 'exports'
            context_variables['export_name'] = context_variables.get('export_name') or 'research_report'
            # Try to infer code extension if code is present
            if 'python' in user_query.lower() or 'py' in user_query.lower():
                context_variables['code_ext'] = 'py'
            elif 'js' in user_query.lower() or 'javascript' in user_query.lower():
                context_variables['code_ext'] = 'js'
            elif 'java' in user_query.lower():
                context_variables['code_ext'] = 'java'
            elif 'cpp' in user_query.lower() or 'c++' in user_query.lower():
                context_variables['code_ext'] = 'cpp'
            else:
                context_variables['code_ext'] = 'py'

        # If this is a follow-up (not the initial research/code query), use the action agent for intent parsing and routing
        if context_variables.get('is_followup', False):
            # Use the action agent to determine intent and route
            action_agent = self.agents['action']
            routed_agent = action_agent.functions[0](context_variables, user_query)
            import inspect
            # If routed_agent is a string (intent label), do not treat as agent
            if isinstance(routed_agent, str):
                # Set output for known actions
                output = None
                if 'export' in user_query.lower():
                    # Determine code extension from user input
                    code_ext = 'py'
                    if 'js' in user_query.lower() or 'javascript' in user_query.lower():
                        code_ext = 'js'
                    elif 'java' in user_query.lower():
                        code_ext = 'java'
                    elif 'cpp' in user_query.lower() or 'c++' in user_query.lower():
                        code_ext = 'cpp'
                    context_variables['code_ext'] = code_ext
                    # Load session for robust export
                    import os, json
                    session_path = context_variables.get('session_path')
                    if session_path and os.path.exists(session_path):
                        with open(session_path, 'r', encoding='utf-8') as f:
                            session_data = json.load(f)
                        context_variables['session'] = session_data
                    # Call formatter's export_to_pdf_and_code
                    formatter = self.agents['formatter']
                    output = formatter.functions[-1](context_variables)
                elif routed_agent == 'run_code':
                    runner = self.agents['runner']
                    runner.functions[0](context_variables)
                    output = context_variables.get('run_output')
                elif routed_agent == 'fix_code':
                    output = context_variables.get('patch_output')
                elif routed_agent == 'add_feature':
                    output = context_variables.get('feature_output')
                elif routed_agent == 'show_code':
                    output = context_variables.get('run_output')
                elif routed_agent == 'show_research':
                    output = context_variables.get('run_output')
                elif routed_agent == 'undo':
                    output = context_variables.get('run_output')
                elif routed_agent == 'show_code_history':
                    output = context_variables.get('run_output')
                elif any(word in user_query.lower() for word in ['reason', 'why', 'explain', 'critique']):
                    reasoner = self.agents['reasoner']
                    output = reasoner.functions[0](context_variables, user_query)
                    history.append({
                        "agent": "ReasonerAgent",
                        "type": "reasoning",
                        "color": "bright_cyan",
                        "output": output or "(No reasoning output)"
                    })
                    if output:
                        from rich.console import Console
                        console = Console()
                        console.print(f'\n[Reasoning]\n{output}\n', style='bold cyan')
                    return context_variables, history
                elif 'debate' in user_query.lower() or 'panel review' in user_query.lower():
                    reasoner = self.agents['reasoner']
                    context_variables['debate'] = True
                    output = reasoner.functions[0](context_variables, user_query)
                    history.append({'agent': 'Reasoner (Panel)', 'output': output})
                elif 'search more deeply' in user_query.lower() or 'swarm' in user_query.lower():
                    researcher = self.agents['researcher']
                    context_variables['swarm_mode'] = True
                    output = researcher.functions[0](context_variables)
                    history.append({'agent': 'Researcher (Swarm)', 'output': output})
                elif 'scrape all sources' in user_query.lower() or 'deep scrape' in user_query.lower():
                    researcher = self.agents['researcher']
                    context_variables['deep_scrape'] = True
                    output = researcher.functions[0](context_variables)
                    history.append({'agent': 'Researcher (Deep Scrape)', 'output': output})
                else:
                    output = context_variables.get('run_output') or context_variables.get('patch_output') or context_variables.get('feature_output') or context_variables.get('project_report') or context_variables.get('generated_code') or context_variables.get('final_answer') or context_variables.get('research_results') or "(No output)"
                history.append({
                    "agent": "ActionAgent",
                    "type": context_variables.get('action_intent', 'action'),
                    "color": "bright_blue",
                    "output": output or "(No output)"
                })
                # Always show the result/output
                if output:
                    from rich.console import Console
                    console = Console()
                    console.print(f'\n[Result]\n{output}\n', style='bold green')
                return context_variables, history
            # If routed_agent is an agent object, proceed as before
            agent_func = routed_agent.functions[0]
            sig = inspect.signature(agent_func)
            try:
                if len(sig.parameters) == 2:
                    agent_func(context_variables, user_query)
                else:
                    agent_func(context_variables)
            except Exception:
                # Fallback: try both signatures
                try:
                    agent_func(context_variables, user_query)
                except Exception:
                    agent_func(context_variables)
            history.append({
                "agent": getattr(routed_agent, 'name', 'UnknownAgent'),
                "type": context_variables.get('action_intent', 'action'),
                "color": "bright_blue",
                "output": context_variables.get('run_output', '') or context_variables.get('patch_output', '') or context_variables.get('feature_output', '') or context_variables.get('project_report', '') or context_variables.get('generated_code', '') or context_variables.get('final_answer', '') or context_variables.get('research_results', '') or "(No output)"
            })
            # After routed agent runs, always show the result/output
            output = context_variables.get('run_output') or context_variables.get('patch_output') or context_variables.get('report_output')
            if output:
                from rich.console import Console
                console = Console()
                console.print(f'\n[Result]\n{output}\n', style='bold green')
            return context_variables, history

        # Enable chain-of-thought mode if requested
        if any(word in user_query.lower() for word in ['step by step', 'chain of thought', 'cot', 'explain your reasoning']):
            context_variables['chain_of_thought'] = True
            history.append({'agent': 'MotherAgent', 'type': 'control', 'color': 'magenta', 'output': 'Chain-of-thought mode enabled for all agents.'})
        # Trigger code critic if requested
        if any(word in user_query.lower() for word in ['critique the code', 'code review', 'code critic']):
            code_critic = self.agents['code_critic']
            output = code_critic.functions[0](context_variables)
            history.append({'agent': 'Code Critic', 'type': 'review', 'color': 'red', 'output': output})

        # 1. Planning
        planner = self.agents['planner']
        planner.functions[0](context_variables, user_query)
        plan = context_variables.get('plan', [])
        history.append({"agent": "Planner", "type": "plan", "color": "cyan", "output": plan})

        # 2. For each step in the plan, route to the correct agent
        for step in plan:
            if not isinstance(step, dict):
                continue
            agent_name = step.get('agent', '').lower()
            task = step.get('task', '')
            reasoning = step.get('reasoning', '')
            # Internal monologue before each step
            internal_monologue = self.agents['internal_monologue']
            monologue = internal_monologue.functions[0](context_variables, f"Step: {task}\nReasoning: {reasoning}")
            history.append({"agent": "Internal Monologue", "type": "reasoning", "color": "grey50", "output": monologue})
            # Route to agent
            if agent_name == 'researcher':
                researcher = self.agents['researcher']
                researcher.functions[0](context_variables)
                history.append({"agent": "Researcher", "type": "research", "color": "yellow", "output": context_variables.get('research_results', '')})
                # Enhanced: Display detailed research info for each sub-query
                research_details = context_variables.get('research_details', [])
                if research_details:
                    details_output = "\n[bold underline]Research Details for Each Sub-query:[/bold underline]\n"
                    for detail in research_details:
                        details_output += f"\n[bold]Query:[/bold] {detail['query']}\n"
                        if detail['ranked_urls']:
                            details_output += "[bold]Ranked URLs Retrieved:[/bold]\n"
                            for idx, url in enumerate(detail['ranked_urls'], 1):
                                details_output += f"  {idx}. {url}\n"
                        if detail['scraping_status']:
                            details_output += "[bold]Scraping Status (per URL):[/bold]\n"
                            for status in detail['scraping_status']:
                                details_output += f"  - {status['url']}: {status['status']}\n"
                        if detail['char_counts']:
                            details_output += "[bold]Characters Scraped (per URL):[/bold]\n"
                            for cc in detail['char_counts']:
                                details_output += f"  {cc['url']}: {cc['chars']} chars\n"
                        details_output += "\n---\n"
                    history.append({
                        "agent": "Researcher",
                        "type": "research_details",
                        "color": "bright_white",
                        "output": details_output
                    })
                # Robust check: if no research was found, halt and print error
                combined_research = context_variables.get('combined_research', '').strip().lower()
                if not combined_research or combined_research in ["research failed due to error", "", "no content could be scraped.", "research failed"] or (len(combined_research) < 100):
                    error_msg = ("[red][bold]No research results were found or all scraping failed. Please try rephrasing your query, check your internet connection, or try again later. No answer or review will be generated.[/bold][/red]")
                    history.append({
                        "agent": "System",
                        "type": "error",
                        "color": "red",
                        "output": error_msg
                    })
                    return context_variables, history
            elif agent_name == 'coder':
                coder = self.agents['coder']
                coder.functions[0](context_variables)
                history.append({"agent": "Coder", "type": "code", "color": "bright_blue", "output": context_variables.get('generated_code', '')})
            elif agent_name == 'formatter':
                formatter = self.agents['formatter']
                formatter.functions[0](context_variables)
                history.append({"agent": "Formatter", "type": "format", "color": "magenta", "output": context_variables.get('formatted_research', '')})
            elif agent_name == 'answer':
                answer = self.agents['answer']
                answer_text = answer.functions[0](context_variables, user_query)
                history.append({"agent": "Answer", "type": "answer", "color": "green", "output": answer_text})
            elif agent_name == 'runner':
                runner = self.agents['runner']
                runner.functions[0](context_variables)
                history.append({"agent": "Runner", "type": "run_code", "color": "bright_yellow", "output": context_variables.get('run_output', '')})
            elif agent_name == 'reporter':
                reporter = self.agents['reporter']
                reporter.functions[0](context_variables)
                history.append({"agent": "Reporter", "type": "report", "color": "bright_magenta", "output": context_variables.get('project_report', '')})
            elif agent_name == 'patcher':
                patcher = self.agents['patcher']
                patcher.functions[0](context_variables)
                history.append({"agent": "Patcher", "type": "patch", "color": "red", "output": context_variables.get('patch_output', '')})
            # Add more agent routing as needed

        # After all steps, always synthesize a final answer
        answer = self.agents['answer']
        answer_text = answer.functions[0](context_variables, user_query)
        history.append({"agent": "Answer", "type": "answer", "color": "green", "output": answer_text})

        # Store in Knowledge Base
        try:
            from src.core.knowledge_base import KnowledgeBase
            kb = KnowledgeBase(qdrant_url='http://localhost:6333', collection_name='research_knowledge')
            point_ids = kb.add_research_result(user_query, answer_text, context_variables.get('sources', []), context_variables.get('session_id'))
            history.append({"agent": "KnowledgeBase", "type": "storage", "color": "blue", "output": f"Stored research result in KB with point_ids: {point_ids}"})
        except Exception as e:
            history.append({"agent": "KnowledgeBase", "type": "storage", "color": "red", "output": f"Failed to store in KB: {e}"})

        # Review (for final answer)
        reviewer = self.agents['reviewer']
        reviewer.functions[0](context_variables)
        history.append({"agent": "Reviewer", "type": "review", "color": "white", "output": context_variables.get('final_answer', '')})

        # Code generation (if needed and not already handled)
        if context_variables.get('needs_code', False) and not any(s.get('agent', '').lower() == 'coder' for s in plan):
            coder = self.agents['coder']
            coder.functions[0](context_variables)
            history.append({"agent": "Coder", "type": "code", "color": "bright_blue", "output": context_variables.get('generated_code', '')})

        # Export if requested
        if export_format:
            reporter = self.agents['reporter']
            reporter.functions[0](context_variables)
            history.append({"agent": "Reporter", "type": "export", "color": "bright_magenta", "output": context_variables.get('project_report', '')})

        return context_variables, history

    def run_code(self, context_variables: dict):
        """Continue the workflow to run the generated code and review the result."""
        history = []
        runner = self.agents['runner']
        runner.functions[0](context_variables)
        history.append({"agent": "Runner", "type": "run_code", "color": "bright_yellow", "output": context_variables.get('run_output', '')})
        reviewer = self.agents['reviewer']
        reviewer.functions[0](context_variables)
        history.append({"agent": "Reviewer", "type": "review", "color": "white", "output": context_variables.get('final_answer', '')})
        return context_variables, history 