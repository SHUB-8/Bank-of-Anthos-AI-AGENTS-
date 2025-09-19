# GENERATED: Orchestrator - produced by Gemini CLI. Do not include mock or dummy data in production code.

# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "uvicorn[standard]"

# Copy the requirements file into the container at /app
COPY ./requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --timeout=100 --retries=5 -r requirements.txt

# Copy the rest of the application's code into the container at /app
COPY . /app

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable
ENV MODULE_NAME="main"
ENV VARIABLE_NAME="app"

# Run uvicorn when the container launches
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
