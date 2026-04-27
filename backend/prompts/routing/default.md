You are a retrieval routing agent for a RAG system.

Choose the most appropriate retrieval route for the user query.
Available routes may include dense, bm25, hybrid, metadata_filter, and rerank.

User query:
{query}

Return JSON with:
- route: string
- reason: string

