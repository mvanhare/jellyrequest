# JellyRequest Bot

A Discord bot for interacting with Jellyseerr and Jellyfin.

## Features

-   Search for media on Jellyseerr.
-   Request media through Jellyseerr.
-   Link Discord user to Jellyseerr/Jellyfin user.
-   View current requests and their status.

## Running with Docker (Manual `docker run`)

This application is designed to be run with Docker. If you prefer manual control with `docker run` commands, follow these instructions. For a simpler setup, see the "Running with Docker Compose" section below.

### Prerequisites

-   Docker installed and running.
-   A Discord Bot Token.
-   Access to a Jellyseerr instance (URL and API Key).
-   Access to a Jellyfin instance (URL and API Key, optional for some features but recommended).

### 1. Build the Docker Image

Navigate to the directory containing the `Dockerfile` and run:

```bash
docker build -t jellyrequest-bot .
```

### 2. Run the Docker Container

You need to provide several environment variables when running the container. You also need to mount a volume to persist the `linked_users.db` SQLite database.

**Environment Variables:**

*   `DISCORD_BOT_TOKEN`: Your Discord bot token. **(Required)**
*   `JELLYSEERR_URL`: The URL for your Jellyseerr instance (e.g., `https://requests.example.com`). **(Required)**
*   `JELLYSEERR_API_KEY`: Your Jellyseerr API key. **(Required)**
*   `JELLYFIN_URL`: The URL for your Jellyfin instance (e.g., `https://media.example.com`). **(Required, or ensure default in code is suitable if not linking to Jellyfin)**
*   `JELLYFIN_API_KEY`: Your Jellyfin API key. **(Required, or ensure default in code is suitable if not linking to Jellyfin)**

**Example `docker run` command:**

Replace the placeholder values with your actual configuration.

```bash
docker run -d \
  --name jellyrequest-bot-container \
  -e DISCORD_BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN" \
  -e JELLYSEERR_URL="YOUR_JELLYSEERR_URL" \
  -e JELLYSEERR_API_KEY="YOUR_JELLYSEERR_API_KEY" \
  -e JELLYFIN_URL="YOUR_JELLYFIN_URL" \
  -e JELLYFIN_API_KEY="YOUR_JELLYFIN_API_KEY" \
  -v $(pwd)/data:/app/data \
  jellyrequest-bot
```

**Explanation of Volume Mounting:**

*   `-v $(pwd)/data:/app/data`: This command creates a directory named `data` in your current working directory on the host machine (`$(pwd)/data`) and maps it to the `/app/data` directory inside the container.
*   The application will store its `linked_users.db` file in `/app/linked_users.db`. To ensure this database is persisted in the `data` directory you just mounted, you should modify `utils.py` to place the database in `/app/data/linked_users.db`.

**Important Note on Database Path:**
The current `utils.py` initializes the database as `sqlite3.connect("linked_users.db")`, which means it will be created in the working directory (`/app` inside the container).

To use the volume mount effectively for the database:
**Option 1 (Recommended for easy host access):** Modify `utils.py` to save the database in a subdirectory that you mount.
   - Change `sqlite3.connect("linked_users.db")` to `sqlite3.connect("data/linked_users.db")` in `utils.py`.
   - Then use the volume mount: `-v $(pwd)/data:/app/data` (as shown in the example). The database will then appear in `./data/linked_users.db` on your host.

**Option 2 (Simpler Docker command, database inside named volume):** Use a named volume for the entire `/app` directory or specifically for the database file if you don't change the path in `utils.py`.
   - If `utils.py` remains unchanged (db in `/app/linked_users.db`):
     ```bash
     docker run -d \
       --name jellyrequest-bot-container \
       # ... your environment variables ...
       -v jellyrequest_bot_db:/app/linked_users.db \
       jellyrequest-bot
     ```
     This creates a Docker named volume `jellyrequest_bot_db` where the database will be stored. It's managed by Docker.

Choose the option that best suits your persistence strategy. Option 1 is often preferred for easier direct access to the database file on the host.

## Running with Docker Compose (Recommended)

Using Docker Compose simplifies the management of the bot's container and its configuration.

### 1. Create an `.env` file

In the same directory as the `docker-compose.yml` file, create a file named `.env`. This file will store your configuration variables.

**`.env` file template:**

```env
# Discord Bot Configuration
DISCORD_BOT_TOKEN=YOUR_DISCORD_BOT_TOKEN_HERE

# Jellyseerr Configuration
JELLYSEERR_URL=https://requests.example.com
JELLYSEERR_API_KEY=YOUR_JELLYSEERR_API_KEY_HERE

# Jellyfin Configuration
JELLYFIN_URL=https://media.example.com
JELLYFIN_API_KEY=YOUR_JELLYFIN_API_KEY_HERE

# Optional: Timezone for container logs (e.g., America/New_York, Europe/London)
# TZ=America/New_York
```

Replace the placeholder values with your actual credentials and URLs.

### 2. Create a `data` directory (if it doesn't exist)

The `docker-compose.yml` is configured to map a local `./data` directory to `/app/data` inside the container. This is where the `linked_users.db` file will be stored.

```bash
mkdir data
```
*(Skip if this directory already exists from previous Docker setups).*

### 3. Start the Bot with Docker Compose

Navigate to the directory containing the `docker-compose.yml` and `.env` files, then run:

```bash
docker-compose up -d
```

This command will:
- Build the Docker image if it hasn't been built already (based on the `Dockerfile`).
- Create and start the container in detached mode (`-d`).
- Load environment variables from your `.env` file.
- Mount the `./data` directory for database persistence.
- Automatically restart the bot if it crashes (due to `restart: unless-stopped`).

### 4. Viewing Logs

To view the bot's logs when using Docker Compose:

```bash
docker-compose logs -f
```

### 5. Stopping the Bot

To stop the bot:

```bash
docker-compose down
```
This will stop and remove the container. The `data` directory (and the database within) will remain on your host.

## Development

(TODO: Add instructions for local development if needed, e.g., setting up a virtual environment, installing dependencies from `requirements.txt`, and running `python jellyrequest.py` directly with environment variables set locally.)

## Contributing

(TODO: Add guidelines for contributing if this were an open project.)
```
