# JellyRequest Bot

A Discord bot for interacting with Jellyseerr and Jellyfin.

## Features

-   Search for media on Jellyseerr.
-   Request media through Jellyseerr.
-   Link Discord user to Jellyseerr/Jellyfin user.
-   View current requests and their status.

## Running with Docker

This application is designed to be run with Docker.

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

## Development

(TODO: Add instructions for local development if needed, e.g., setting up a virtual environment, installing dependencies from `requirements.txt`, and running `python jellyrequest.py` directly with environment variables set locally.)

## Contributing

(TODO: Add guidelines for contributing if this were an open project.)
```
