# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container at /app
# Copy individual files and the cogs directory
COPY jellyrequest.py .
COPY utils.py .
COPY cogs/ ./cogs/

# Define the command to run the application
CMD ["python", "jellyrequest.py"]