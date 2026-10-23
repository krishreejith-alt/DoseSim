# DoseSim environment image.
# Default command runs the full test suite + quality gates (a self-check).
# To serve one task over MCP (stdio):
#   docker run -i -e DOSESIM_TASK=tasks/vanc/dose-vanc-0002.json dosesim python -m dosesim.mcp_server
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY dosesim ./dosesim
COPY tasks ./tasks
COPY scripts ./scripts
COPY tests ./tests
COPY validation ./validation
# Private reference answers never go into the image
RUN rm -f tasks/vanc_solutions.json
CMD ["sh", "-c", "python -m pytest -q tests && python -m scripts.check_tasks"]
