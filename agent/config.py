"""Choose the LLM backend: OpenRouter if a key is present, otherwise a local Ollama."""


def resolve_backend(env) -> tuple[str, str | None]:
    if env.get("OPENROUTER_API_KEY"):
        return env.get("LLM_MODEL", "openrouter/google/gemini-2.5-flash"), None
    return (
        env.get("OLLAMA_MODEL", "ollama_chat/qwen3:8b"),
        env.get("OLLAMA_API_BASE", "http://localhost:11434"),
    )
