"""relevance.py — single source of truth for "is this story actually about AI?".

The old filter matched query words as substrings, so "AI LLM models news
releases" matched "N**ai**ls", "**Ai**rbus" and "SideWinder". Word boundaries
plus an explicit AI vocabulary keep non-AI front-page noise out.
"""

import re

AI_TERMS = re.compile(
    r"\b(?:a\.?i\.?|agi|llms?|gpt[-\s]?\d|chatgpt|claude|gemini|llama|qwen|"
    r"deepseek|kimi|mistral|grok|phi-?\d|nemotron|gemma|transformers?|"
    r"neural|machine learning|deep learning|openai|anthropic|deepmind|"
    r"hugging\s?face|diffusion|fine-?tun\w*|inference|embeddings?|"
    r"rag|agentic|ai agents?|mcp|copilot|cursor|model weights|"
    r"large language model|foundation model|open-weights?|"
    r"reasoning model|multimodal|text-to-\w+|llmops|vllm|ollama|llama\.cpp|"
    r"language models?)\b",
    re.IGNORECASE,
)


def is_ai_relevant(*texts: str) -> bool:
    """True when any supplied text mentions AI vocabulary as a whole word.

    shortcut: keyword-only, so an AI-adjacent business headline that never
    names AI ("Databricks raises at a $225B valuation") is dropped. Upgrade to
    an LLM classifier if that recall loss starts to matter.
    """
    return any(AI_TERMS.search(t or "") for t in texts)
