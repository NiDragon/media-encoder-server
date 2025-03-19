# Use Alpine Linux as the base image
FROM alpine:latest

# Install necessary packages
RUN apk add --no-cache \
    ffmpeg \
    python3 \
    py3-virtualenv \
    py3-pip

# Copy application files to the container
COPY main.py /app/main.py
COPY requirements.txt /app/requirements.txt

# Set the working directory inside the container
WORKDIR /app

# Setup the python virtual env
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Install pip packages
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Ensure the Python script is executable
RUN chmod +x /app/main.py

# Open the port for rpc
EXPOSE 5000

# Command to execute the application and exit upon completion
CMD ["python3", "/app/main.py"]
