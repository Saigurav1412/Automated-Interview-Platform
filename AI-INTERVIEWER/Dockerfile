# AI interviewer voice agent (LiveKit worker)
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ src/

# Pre-download model weights (Silero VAD etc.) so the first interview starts fast
RUN python src/main.py download-files

# Run as a non-root user
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# The resume PDF is read from this path; mount it with -v /path/resume.pdf:/app/resume.pdf:ro
ENV GUI_RESUME_PATH=/app/resume.pdf

# API keys come from the environment (--env-file .env); none are baked into the image
CMD ["python", "src/main.py", "start"]
