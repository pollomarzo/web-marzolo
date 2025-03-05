FROM python:3.11-slim

WORKDIR /app

# Install git and setup entrypoint
RUN apt-get update && \
    apt-get install -y git openssh-client && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY *.py .
COPY README.md .

# Create required directories
RUN mkdir -p /app/config /app/data/bot_gen

# Use non-root user
RUN useradd -m -d /home/botuser -s /bin/bash botuser && \
    mkdir -p /home/botuser/.ssh && \
    chmod 700 /home/botuser/.ssh && \ 
    chown -R botuser:botuser /app

USER botuser

WORKDIR /repo

# Environment variables
ENV PYTHONPATH=/app
ENV ALLOWED_FOLDER=/repo/src/bot_gen

RUN echo '#!/bin/bash\ngit config --global user.email "${GIT_BOT_EMAIL}"\ngit config --global user.name "${GIT_BOT_USER}"\nexec "$@"' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["python", "thoughts_bot.py"]
