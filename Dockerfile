FROM python:3.10-slim

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install basic system dependencies and Xvfb
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    xvfb \
    procps \
    curl \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libxss1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Download and install Google Chrome Stable directly from Google
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && dpkg -i google-chrome-stable_current_amd64.deb || apt-get install -fy \
    && rm google-chrome-stable_current_amd64.deb

# Verify Google Chrome installation
RUN google-chrome --version

# Set up the application workspace
WORKDIR /app

# Copy dependency definition and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files, credentials, and configuration
COPY sheet_alibaba_inquiry.py .
COPY cookies.json .
COPY instagram-credentials.json .
COPY entrypoint.sh .

# Ensure entrypoint.sh is executable and has Unix line endings
RUN chmod +x entrypoint.sh \
    && sed -i 's/\r$//' entrypoint.sh

# Run entrypoint.sh to start Xvfb and then run the Python bot
ENTRYPOINT ["./entrypoint.sh"]
