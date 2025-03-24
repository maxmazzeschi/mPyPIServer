FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port (default 5000)
EXPOSE 5000

# Set environment variables for package folder and port
ENV PACKAGE_FOLDER=/app/packages
ENV LISTEN_PORT=8082

# Run the app using Gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:${LISTEN_PORT}", "app:app"]
