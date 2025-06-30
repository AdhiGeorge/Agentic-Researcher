from swarm import Agent
from . import get_prompt
import re
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
from fpdf import FPDF

def is_relevant_result(result):
    # Only filter out truly empty or junk results
    info = result.get('info', '').strip()
    return bool(info)

def format_research(context_variables):
    """
    Concatenate all relevant scraped info, with minimal filtering, and pass everything to the answer agent.
    Do not summarize or strip code blocks. Add clear section headers for each query, but otherwise preserve all content.
    """
    research_results = context_variables.get('research_results', [])
    filtered = [r for r in research_results if is_relevant_result(r)]
    if not filtered:
        context_variables['formatted_research'] = "No highly relevant research results found."
        context_variables['needs_code'] = 'code' in context_variables.get('query', '').lower()
        return "No highly relevant research results found."
    summary_lines = ["# Full Research Content\n"]
    all_sources = set()
    for r in filtered:
        query = r.get('query', '').strip()
        info = r.get('info', '').strip()
        sources = r.get('sources', [])
        if query:
            summary_lines.append(f"## Query: {query}\n")
        if info:
            summary_lines.append(info + "\n")
        for s in sources:
            if s:
                all_sources.add(s)
        summary_lines.append("\n---\n")
    if all_sources:
        summary_lines.append("\n## Sources:")
        for s in sorted(all_sources):
            summary_lines.append(f"- {s}")
    formatted = "\n".join(summary_lines)
    user_query = context_variables.get('query', '').lower()
    context_variables['needs_code'] = any(word in user_query for word in ['code', 'python', 'script', 'implementation'])
    context_variables['formatted_research'] = formatted
    return formatted

def extract_research_sections(context_variables):
    # Only include main research/answer sections, not plans or system messages
    research_sections = []
    for key, value in context_variables.items():
        if key in ('plan', 'history', 'session', 'export_format', 'export_path', 'export_name', 'code_ext', 'run_output', 'patch_output', 'feature_output', 'project_report', 'final_answer', 'generated_code', 'formatted_research', 'action_intent', 'last_error', 'execution_successful', 'pdf_export_path'):
            continue
        if isinstance(value, str) and len(value.strip()) > 0:
            # Try to parse as JSON for nested 'response' fields
            if value.strip().startswith('{'):
                try:
                    import json
                    obj = json.loads(value)
                    if 'response' in obj:
                        research_sections.append(obj['response'])
                except Exception:
                    research_sections.append(value)
            else:
                research_sections.append(value)
        elif isinstance(value, dict):
            for v in value.values():
                if isinstance(v, str) and len(v.strip()) > 0:
                    research_sections.append(v)
    # Also check for session/history fields for main research/answer only
    if isinstance(context_variables.get('session'), list):
        for entry in context_variables['session']:
            if entry.get('agent') in ('Answer', 'Researcher', 'Reporter') and isinstance(entry.get('output'), str):
                research_sections.append(entry['output'])
    return research_sections

def extract_latest_code_block(context_variables, language='python'):
    # Search for the latest code block in research/answer sections
    code_blocks = []
    pattern = rf'```{language}\\s*(.*?)```'
    for section in extract_research_sections(context_variables):
        code_blocks += re.findall(pattern, section, re.DOTALL)
    return code_blocks[-1] if code_blocks else None

def export_to_pdf_and_code(context_variables, pdf_output_path=None, code_output_path=None):
    try:
        from fpdf import FPDF
    except ImportError:
        return "Error: FPDF library is not installed. Please run 'pip install fpdf'."
    # Determine export paths
    export_dir = context_variables.get('export_path', 'exports')
    os.makedirs(export_dir, exist_ok=True)
    pdf_output_path = pdf_output_path or os.path.join(export_dir, 'research_report.pdf')
    code_ext = context_variables.get('code_ext', 'py')
    code_output_path = code_output_path or os.path.join(export_dir, f'vix_calculation.{code_ext}')
    # 1. Export research data to PDF
    research_sections = extract_research_sections(context_variables)
    if not research_sections:
        pdf_result = 'No research data found to export.'
    else:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        for section in research_sections:
            # Remove code blocks for readability
            cleaned = re.sub(r'```[a-zA-Z0-9]*.*?```', '', section, flags=re.DOTALL)
            for line in cleaned.split('\n'):
                pdf.multi_cell(0, 10, line)
            pdf.ln(5)
        try:
            pdf.output(pdf_output_path)
            pdf_result = f"PDF exported successfully to {pdf_output_path}"
            context_variables['pdf_export_path'] = pdf_output_path
        except Exception as e:
            pdf_result = f"Error generating PDF: {str(e)}"
    # 2. Export code to correct language file
    language = code_ext if code_ext != 'py' else 'python'
    code = extract_latest_code_block(context_variables, language=language)
    if code:
        try:
            with open(code_output_path, 'w', encoding='utf-8') as f:
                f.write(code.strip() + '\n')
            code_result = f"Code exported successfully to {code_output_path}"
            context_variables['code_export_path'] = code_output_path
        except Exception as e:
            code_result = f"Error exporting code: {str(e)}"
    else:
        code_result = f"No {language} code found to export."
    return f"{pdf_result}\n{code_result}"

formatter_agent = Agent(
    name="Formatter Agent",
    instructions=get_prompt('formatter'),
    functions=[format_research, export_to_pdf_and_code],
) 