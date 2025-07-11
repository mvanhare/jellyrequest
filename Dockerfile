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

# Expose the port the app runs on (if any, for Discord bots this is not typical for incoming HTTP)
# No port needs to be exposed for a Discord bot unless it also runs a web server.

# Define the command to run the application
CMD ["python", "jellyrequest.py"]

# Note on database:
# The linked_users.db will be created in /app/linked_users.db within the container.
# To persist this database, a volume should be mapped to /app/linked_users.db
# when running the container. Example:
# docker run -v /path/on/host/linked_users.db:/app/linked_users.db ... your_image_name
# Or, using a named volume:
# docker run -v jellybot_data:/app/linked_users.db ... your_image_name
# (and the volume would typically map to /app if you want the whole dir,
# but for just the db, mapping it directly is fine, or map ./data:/app/data and adjust db path in code)
# For this setup, we assume linked_users.db is in the WORKDIR /app.
