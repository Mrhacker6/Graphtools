# ToolBot — Multi-Actor Chatbot with LangGraph and Tool Integrations

Version: 1.0.0  
Last updated: 2026-01-01

Table of contents
- Overview
- Key concepts
- Features
- Architecture & data flow
- Actors (roles)
- Tool integrations
  - arXiv
  - Wikipedia
  - DuckDuckGo Instant Answer
- LangGraph orchestration (design + examples)
- Installation & quick start
- Configuration (secrets, endpoints, rate limits)
- Example conversation flows
- Prompt templates & actor instructions
- Caching, rate-limiting, and privacy
- Testing & validation
- Observability & monitoring
- Deployment patterns
- Troubleshooting
- Roadmap
- Contributing & license
---

## Overview
ToolBot is a multi-actor conversational assistant designed to answer research and general-knowledge queries by orchestrating specialized actors using LangGraph. Each actor focuses on a capability (e.g., querying arXiv for papers, retrieving encyclopedia summaries from Wikipedia, and running broad web searches via DuckDuckGo), and a synthesizer actor merges their responses into a coherent reply for the user.

Goals:
- Provide accurate, sourced answers for research and factual queries.
- Maintain modular, auditable tool usage via LangGraph graphs.
- Allow easy extension with new tools/actors and safe fallbacks.

Audience: developers and maintainers who want to run, extend, or embed ToolBot; also useful for researchers evaluating automated tool-based agents.

---

## Key concepts

- Actor: single-purpose conversational agent (e.g., ResearchActor) with its own prompt/template and tool access.
- Tool: external data source or API (arXiv, Wikipedia, DuckDuckGo Instant Answer).
- LangGraph: orchestrator that defines nodes and edges; runs the multi-actor flow, controls tool calls, routing, and aggregation.
- Router: LangGraph node that inspects user intent and routes queries to one or more actors.
- Synthesizer: actor/node that reconciles outputs, resolves contradictions, and builds the final message with citations.

---

## Features
- Multi-actor architecture (specialized actors for different knowledge domains).
- Tool-backed retrieval (arXiv for papers, Wikipedia for encyclopedic context, DuckDuckGo for broad web signals).
- LangGraph-managed orchestration (graph nodes, retries, parallel calls).
- Source-aware responses with citations and link-back.
- Caching layer to reduce duplicate API calls and respect rate limits.
- Configurable policies for hallucination reduction, freshness, and source preference.

---

## Architecture & data flow

1. User submits query to ToolBot API / web UI.
2. Router node (LangGraph) runs intent classification + tool-selection rules.
3. Selected actors are invoked—some in parallel:
   - ResearchActor -> arXiv tool
   - EncyclopediaActor -> Wikipedia tool
   - SearchActor -> DuckDuckGo tool
4. Each actor returns: content snippet(s), structured metadata (title, authors, URL, timestamp), confidence score, and raw tool traces.
5. SynthesizerActor collects outputs, deduplicates, ranks by relevance/confidence, and composes the final answer with explicit citations and an activities log.
6. Response returned to user with visible sources and optional "show raw data" toggle.

Diagram (conceptual):
User -> Router (LangGraph) -> [Actor A: arXiv, Actor B: Wikipedia, Actor C: DuckDuckGo] -> Synthesizer -> User

---

## Actors (roles)

- RouterActor
  - Responsibility: intent detection, decide which domain actors to call, optionally set timeouts and max results per tool.
- ResearchActor (arXiv)
  - Responsibility: find relevant papers, extract abstracts, authors, PDF links, summarise findings.
- EncyclopediaActor (Wikipedia)
  - Responsibility: fetch summary paragraphs, notable dates/facts, relevant section links.
- SearchActor (DuckDuckGo)
  - Responsibility: quick web-fact-checks and non-scholarly context (news, blogs, FAQs).
- SynthesizerActor
  - Responsibility: combine the above outputs, detect contradictions, provide final human-facing answer with citations and confidence.
- SafetyActor (optional)
  - Responsibility: content filtering, remove or flag restricted content, policy enforcement.

Each actor should log tool usage, raw inputs and outputs, and confidence metadata.

---

## Tool integrations

General guidelines for tool wrappers:
- Wrap each external API in a small adapter that standardizes outputs to a ToolResponse:
  - { id, title, snippet, url, created_at, authors, source, raw_payload, confidence_score }
- Always sanitize tool outputs and normalize date/time and URL formats.
- Add retry/backoff and circuit-breaker behavior to protect from transient failures.

### arXiv (research papers)
- Purpose: find and retrieve scholarly preprints relevant to technical questions.
- API:
  - arXiv provides an Atom-based API. Example search: https://export.arxiv.org/api/query?search_query=all:"neural+networks"&start=0&max_results=5
  - Prefer using arXiv OAI/Atom or maintained client libraries.
- Best practices:
  - Request only titles, authors, abstract, published date, and PDF link.
  - Return arXiv ID and canonical url: https://arxiv.org/abs/{id}
  - Cache results for at least 24 hours (papers rarely change).
  - Respect arXiv rules and rate limits; add a proper User-Agent string.

Example arXiv adapter (pseudo-JSON result):
{
  "id":"arXiv:2101.00001",
  "title":"Example Title",
  "authors":["A. Author"],
  "abstract":"Short abstract...",
  "url":"https://arxiv.org/abs/2101.00001",
  "pdf":"https://arxiv.org/pdf/2101.00001.pdf",
  "published":"2021-01-01T00:00:00Z",
  "source":"arXiv"
}

### Wikipedia
- Purpose: provide short authoritative background and definitions.
- API: MediaWiki REST API
  - Example summary: https://en.wikipedia.org/api/rest_v1/page/summary/Neural_network
  - For sections: https://en.wikipedia.org/w/api.php?action=parse&page=Neural_network&prop=text&format=json
- Best practices:
  - Prefer the `page/summary` endpoint for concise content and structured data (extract, description).
  - Include the page URL and last revision date.
  - Cite sections and provide the exact URL to the section when possible.
  - Respect Wikimedia caching and attribution requirements.

Example Wikipedia adapter output:
{
  "title":"Neural network",
  "extract":"A neural network is ...",
  "url":"https://en.wikipedia.org/wiki/Neural_network",
  "last_revised":"2025-12-01T12:00:00Z",
  "source":"Wikipedia"
}

### DuckDuckGo Instant Answer (web search + quick facts)
- Purpose: quick web facts, disambiguation, and signals from the broader web (non-Google alternative).
- API endpoints:
  - Instant Answer API: https://api.duckduckgo.com/?q=neural+networks&format=json&no_redirect=1&no_html=1
  - Note: this is not a full web-search API; for broader results you may need third-party indexed search wrappers.
- Best practices:
  - Use for lightweight fact-checks, disambiguation, and to find links to news or blog content.
  - Combine with other tools for depth (DuckDuckGo alone may be terse).
  - Handle cases with no results gracefully.

Example DuckDuckGo response normalized:
{
  "query":"neural networks",
  "heading":"Neural network",
  "abstract":"Neural networks are ...",
  "related_topics":[...],
  "source":"DuckDuckGo"
}

---

## LangGraph orchestration (design + examples)
LangGraph will be the runtime that defines nodes (actors), edges, and orchestration policies. The graph should be versioned and auditable.

High-level LangGraph design:
- Node: Router (text classifier)
- Parallel nodes: ResearchActor, EncyclopediaActor, SearchActor (run in parallel, with timeouts)
- Aggregation node: Synthesizer (inputs from parallel nodes)
- Optional: Safety node (validate result)

Example graph pseudo-YAML (conceptual — adapt to your LangGraph spec):
```yaml
graph:
  id: toolbot_v1
  nodes:
    - id: router
      type: function
      runtime: llm
      instruction: |
        Determine which actors (research, encyclopedia, search) are needed for the user's query.
        Return JSON: { "route": ["research","encyclopedia"], "max_results": {research:3, encyclopedia:1, search:2} }
    - id: research
      type: actor
      tool: arxiv_adapter
      concurrency: parallel
      timeout: 8s
      inputs: from(router.route) when includes research
    - id: encyclopedia
      type: actor
      tool: wikipedia_adapter
      timeout: 3s
      inputs: from(router.route) when includes encyclopedia
    - id: search
      type: actor
      tool: duckduckgo_adapter
      timeout: 3s
      inputs: from(router.route) when includes search
    - id: synthesizer
      type: function
      runtime: llm
      inputs: [research, encyclopedia, search]
      instruction: |
        Combine results into a concise answer. Provide bullets: key findings, citations (with direct URLs), confidence score (0-1), and "raw_traces" showing which tool produced which snippet.
  edges:
    - from: router
      to: [research, encyclopedia, search]
    - from: [research, encyclopedia, search]
      to: synthesizer
```

Notes:
- Use parallel execution for speed; set per-node timeouts.
- The router's decision should be logged for traceability.
- The synthesizer should include raw tool traces and confidence metadata in the response.

LangGraph runtime-specific tips:
- Version graphs and pin to a graph revision in production.
- Limit maximum tokens for LLM prompts in nodes that do summarization to control costs.
- Capture tool call metadata in LangGraph's trace logs for auditing.

---

## Installation & quick start

Prerequisites:
- Node 18+ or Python 3.10+
- Docker (optional, recommended)
- LangGraph runtime installed and configured (see their docs)
- API keys (if needed) and network access to external APIs

Quick start (conceptual steps):
1. Clone repository:
   git clone https://github.com/your-org/toolbot.git
2. Copy example config and provide credentials:
   cp config.example.yaml config.yaml
   # Edit config.yaml to set endpoints and keys
3. Install dependencies:
   npm install
   # or
   pip install -r requirements.txt
4. Start local LangGraph runtime (or connect to hosted LangGraph):
   langgraph start --config langgraph.config.yaml
5. Start ToolBot server:
   npm run dev
6. Open the UI at http://localhost:3000 or call the API endpoint POST /api/chat with { "input": "Your question" }

Important: Replace above commands with your repo's actual start commands. This section assumes you have a LangGraph runtime accessible.

---

## Configuration (secrets, endpoints, rate limits)

Example config.yaml keys:
- langgraph:
  - endpoint: "https://langgraph.example/api"
  - api_key: "..."
- tools:
  - arxiv:
    - base_url: "https://export.arxiv.org/api/query"
    - user_agent: "ToolBot/1.0 (+https://your-org.example)"
    - max_per_query: 5
  - wikipedia:
    - base_url: "https://en.wikipedia.org/api/rest_v1/page/summary"
  - duckduckgo:
    - base_url: "https://api.duckduckgo.com"
- cache:
  - redis_url: "redis://localhost:6379/0"
  - ttl_seconds: 86400
- limits:
  - per_tool_rate_limit: 10req/s (adjust per tool)
  - global_concurrency: 8
- safety:
  - content_policy_url: "https://your-org.example/policy"

Security tips:
- Never commit API keys.
- Use environment variables or secret managers.
- Set strict outbound firewall rules in production.

Rate limiting:
- Use token-bucket for each tool adapter.
- Implement exponential backoff on 429s.
- Cache identical queries to avoid repeated calls.

---

## Example conversation flows

1) Research question (user asks for latest papers)
User: "What recent arXiv papers discuss transformers for protein folding?"

Flow:
- Router decides: research
- ResearchActor calls arXiv with specialized query: "transformer protein folding"
- ResearchActor returns top 3 papers (title, abstract snippet, url, pdf)
- Synthesizer summarizes key methods, lists citations, suggests "further reading" links.

Example final answer excerpt:
- Summary: "Recent work applies transformer-based architectures to protein structure prediction; top papers include X (2025) — key idea: ... [arXiv:xxxx.xxxxx]"
- Citations: numbered list with arXiv links and PDF.

2) Factual background + web context
User: "What is CRISPR and has it been used to treat humans?"

Flow:
- Router routes to encyclopedia and search
- EncyclopediaActor fetches Wikipedia summary for "CRISPR"
- SearchActor fetches DuckDuckGo instant answers and links to news about clinical trials
- Synthesizer merges and provides citations: Wikipedia for definition, news links for clinical usage, and confidence level.

---

## Prompt templates & actor instructions

Router prompt (example):
"You are a router: classify the user query into one or more of the following: research, encyclopedia, search. Return JSON array of routes and suggested max_results per tool. Rules: if query mentions 'paper', 'arXiv', 'study', prefer 'research'. If asking 'what is' or definition, include 'encyclopedia'."

ResearchActor prompt (example):
"You are ResearchActor. Use the arXiv tool to find scholarly preprints relevant to the user's query. Return up to {max_results} papers with title, short (1-2 sentence) summary, url, pdf, and confidence between 0 and 1. If results are none, return empty list."

Synthesizer prompt (example):
"You are Synthesizer. Combine inputs from multiple actors. Produce:
1) short answer (2-4 sentences)
2) bullets with key points
3) numbered citations in the text mapping to tool responses (include URL)
4) confidence score (0-1)
5) raw_traces (which tool produced which snippet)
If actors conflict, prefer peer-reviewed / arXiv > Wikipedia > DuckDuckGo. Flag contradictory claims under 'Notes:'."

Always keep prompts deterministic where needed and limit token length.

---

## Caching, rate-limiting, and privacy

Caching:
- Cache tool responses keyed by normalized query + tool name.
- TTLs:
  - arXiv: 24–72 hours
  - Wikipedia: 4–24 hours (Wikipages can change)
  - DuckDuckGo: 1–4 hours
- Respect cache-control headers when present.

Rate-limiting:
- Per-tool token bucket.
- Global concurrency limits for LangGraph nodes.
- Retry on transient failures with exponential backoff and jitter.

Privacy:
- No PII should be sent to tools unless absolutely necessary.
- Log redaction: redact user PII in stored traces.
- Provide a retention policy for logs and cache.

---

## Testing & validation

Unit tests:
- Adapter unit tests: simulate API responses; assert normalized structure.
- Router tests: sample queries map to expected routes.
- Synthesizer tests: given multiple tool inputs, ensure correct aggregation and citation format.

Integration tests:
- Local LangGraph run with mock adapters to test the full graph.
- End-to-end tests for important flows (e.g., "find arXiv papers on X" -> expect non-empty results).

Human evaluation:
- Create a set of golden questions and human-annotated expected answers and sources.
- Periodically run automatic scoring (precision of citations, factuality checks).

---

## Observability & monitoring

Telemetry:
- Track tool usage counts, latencies, error rates, and reasons for routing decisions.
- Capture distribution of actor confidence scores.
- Expose per-graph execution traces for debugging.

Dashboard suggestions:
- Requests per minute
- Tool error rates and 95th percentile latencies
- Cache hit ratio
- Most common routing patterns

Auditing:
- Persist raw_traces (tool inputs and outputs) with limited retention for auditability and debugging.
- Ensure logs are access-controlled.

---

## Deployment patterns

- Single-host (small scale): Docker Compose with local LangGraph runtime and Redis cache.
- Production: Kubernetes
  - Separate deployments: toolbot-api, langgraph-runtime (if self-hosted), redis, ingress, observability stack (Prometheus + Grafana).
  - Autoscale actor workers based on concurrency and queue depth.

Secrets:
- Use a secret manager (AWS Secrets Manager / HashiCorp Vault) for API keys.

CI:
- Linting, unit tests, integration tests against a LangGraph test harness.
- Graph schema validation step before deploying new graph revisions.

---

## Troubleshooting

Problem: No arXiv results returned
- Check arXiv adapter network connectivity and query encoding.
- Check rate-limit / 429 logs.
- Ensure router included research route.

Problem: Synthesizer outputs contradictory statements
- Inspect raw_traces. If contradictions originate from tools, consider adding a conflict-resolution policy or prefer higher-confidence sources.
- Add more explicit prompts for the synthesizer to prefer peer-reviewed content for research claims.

Problem: High latency
- Verify that parallelization is enabled in LangGraph and per-node timeouts are reasonable.
- Use caching to reduce repeated calls for the same queries.

---

## Roadmap
- Add more scholarly sources (PubMed, Semantic Scholar).
- Add a "citation-checker" actor to verify claims against primary sources.
- Add user-customizable source preferences (e.g., prefer textbooks).
- Add conversational memory & personalization layer.

---

## Contributing & license
- Contributions welcome via PR; follow the repo's CONTRIBUTING.md.
- Provide unit tests for new adapters and update graph versioning.
- License: MIT (or choose your project's license)

---

## Example responses & UI suggestions

UI should show:
- Short answer (2-3 lines)
- "Details" expandable: bullets + citations
- Source badges: [arXiv], [Wikipedia], [DuckDuckGo]
- "View raw traces" (for debugging)
- "Show PDFs / open links" buttons
- Confidence indicator and “Why these sources?” explanation

Example final JSON response shape from ToolBot API:
```json
{
  "answer": "Short summary...",
  "bullets": ["Key point 1", "Key point 2"],
  "citations": [
    { "id": "1", "title": "Paper A", "url": "...", "source": "arXiv" },
    { "id": "2", "title": "CRISPR", "url": "...", "source": "Wikipedia" }
  ],
  "confidence": 0.86,
  "raw_traces": {
    "arXiv": [{ "query":"...", "results":[...] }],
    "Wikipedia":[...],
    "DuckDuckGo":[...]
  }
}
```

---

If you'd like, I can:
- generate concrete LangGraph graph YAML for your runtime,
- scaffold adapter code (Node/TypeScript or Python) for arXiv, Wikipedia, and DuckDuckGo,
- or produce example prompts tuned for a specific LLM provider.

Which would you like next?
