FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (for geopandas/shapely)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy source code
COPY . /app/

# Expose Streamlit port
EXPOSE 8501

# Start the dashboard
CMD ["streamlit", "run", "ui/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
