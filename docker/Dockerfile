# One image for the MCP server, the three agents and the orchestrator; compose picks the command.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv
WORKDIR /app
COPY pyproject.toml ./
COPY mcp_server ./mcp_server
COPY agent ./agent
COPY a2a_agents ./a2a_agents
COPY orchestrator ./orchestrator
COPY scripts ./scripts
RUN uv pip install --system --no-cache .
