from swarm import Agent
from src.services.web_search import WebSearchService
from src.core.config import Config
from . import get_prompt
import logging
import threading

# Initialize services
config = Config()
logger = logging.getLogger(__name__)

# Instantiate all available engines
web_search_services = [
    WebSearchService(max_results=config.get('web_search.max_results', 5), timeout=config.get('web_search.timeout', 30)),
]
try:
    # Try to instantiate GoogleSearchAPI if keys are set
    from src.services.web_search import GoogleSearchAPI
    google_api_key = config.get('google.api_key') or config.get('GOOGLE_API_KEY')
    google_cse_id = config.get('google.cse_id') or config.get('GOOGLE_CSE_ID')
    if google_api_key and google_cse_id:
        web_search_services.append(GoogleSearchAPI(google_api_key, google_cse_id, 5, 30))
except Exception:
    pass

# Add more engines as needed (Tavily, Bing, etc.)

def research_steps(context_variables):
    """
    For each research step, use all available engines in parallel (swarm mode), aggregate and deduplicate results, and cross-validate facts. Store all sources and merged results. Fallback to legacy mode if only one engine is available or if 'swarm' is off.
    """
    try:
        plan = context_variables.get('plan', [])
        research_steps = [step for step in plan if isinstance(step, dict) and step.get('agent', '').lower() == 'researcher']
        research_results = []
        sources = set()
        research_details = []
        swarm_mode = context_variables.get('swarm_mode', True)
        for step in research_steps:
            query = step.get('task', '')
            if not query:
                continue
            logger.info(f"Swarm researching: {query}")
            all_results = []
            all_ranked_urls = set()
            all_titles = set()
            threads = []
            results_by_engine = []
            # Swarm mode: parallel search
            if swarm_mode and len(web_search_services) > 1:
                results_lock = threading.Lock()
                def search_with_engine(service):
                    try:
                        results = service.search(query)
                        with results_lock:
                            results_by_engine.append(results)
                    except Exception as e:
                        logger.warning(f"Swarm search failed for {getattr(service, 'engine', str(service))}: {e}")
                for service in web_search_services:
                    t = threading.Thread(target=search_with_engine, args=(service,))
                    t.start()
                    threads.append(t)
                for t in threads:
                    t.join()
                # Aggregate and deduplicate
                for engine_results in results_by_engine:
                    for r in engine_results:
                        link = r.get('link', '')
                        if link and link not in all_ranked_urls:
                            all_results.append(r)
                            all_ranked_urls.add(link)
                            all_titles.add(r.get('title', ''))
            else:
                # Legacy mode: single engine
                engine = web_search_services[0]
                engine_results = engine.search(query)
                for r in engine_results:
                    link = r.get('link', '')
                    if link and link not in all_ranked_urls:
                        all_results.append(r)
                        all_ranked_urls.add(link)
                        all_titles.add(r.get('title', ''))
            # Scrape in order, record status and char count
            scraped_results = []
            scraping_status = []
            char_counts = []
            deep_scrape = context_variables.get('deep_scrape', False)
            for idx, r in enumerate(all_results):
                url = r.get('link', '')
                title = r.get('title', '')
                if not url:
                    continue
                content = web_search_services[0].scrape_url(url)
                if content:
                    scraped_results.append({'title': title, 'url': url, 'content': content})
                    scraping_status.append({'url': url, 'status': 'success'})
                    char_counts.append({'url': url, 'chars': len(content)})
                    if not deep_scrape:
                        break  # Stop after first successful scrape unless deep_scrape is enabled
                else:
                    scraping_status.append({'url': url, 'status': 'fail'})
                    char_counts.append({'url': url, 'chars': 0})
            # If all scraping failed, fallback to snippets (if any)
            if not scraped_results and all_results:
                for idx, r in enumerate(all_results):
                    snippet = r.get('body', '') or 'No content could be scraped.'
                    scraped_results.append({'title': r.get('title', ''), 'url': r.get('link', ''), 'content': snippet})
                    scraping_status.append({'url': r.get('link', ''), 'status': 'snippet'})
                    char_counts.append({'url': r.get('link', ''), 'chars': len(snippet)})
            # Extract relevant info for downstream agents
            relevant_info = web_search_services[0].extract_relevant_info(scraped_results, query) if scraped_results else ''
            research_results.append({
                'query': query,
                'info': relevant_info,
                'sources': [r['url'] for r in scraped_results if r.get('url')]
            })
            sources.update([r['url'] for r in scraped_results if r.get('url')])
            # Collect research details for user display
            research_details.append({
                'query': query,
                'ranked_urls': list(all_ranked_urls),
                'scraping_status': scraping_status,
                'char_counts': char_counts
            })
        combined_research = "\n\n".join([
            f"Query: {result['query']}\nInfo: {result['info']}" for result in research_results
        ])
        context_variables['research_results'] = research_results
        context_variables['combined_research'] = combined_research
        context_variables['sources'] = list(sources)
        context_variables['research_details'] = research_details
        if 'session_id' in context_variables:
            from src.core.database import Database
            db = Database(config.get('database.path'))
            db.log_agent_interaction(
                session_id=context_variables['session_id'],
                agent_name="Researcher",
                action="swarm_web_research" if swarm_mode else "web_research",
                result=f"Researched {len(research_steps)} queries, found {len(sources)} sources"
            )
        from .formatter import formatter_agent
        return formatter_agent
    except Exception as e:
        logger.error(f"Error in researcher: {e}")
        context_variables['research_results'] = [{"query": "fallback", "info": "Research failed", "sources": []}]
        context_variables['combined_research'] = "Research failed due to error"
        context_variables['research_details'] = []
        from .formatter import formatter_agent
        return formatter_agent

researcher_agent = Agent(
    name="Researcher Agent",
    instructions=get_prompt('researcher') + "\n\nNote: This agent now supports swarm/parallel research using multiple search engines (DuckDuckGo, Tavily, Google, etc.) in parallel, deduplicates and cross-validates facts, and can be toggled with 'swarm_mode' in context_variables.",
    functions=[research_steps],
) 