# JellyRequest Bot

A Discord bot for interacting with Jellyseerr and Jellyfin.

## Features

-   Search for media on Jellyseerr.
-   Request media through Jellyseerr.
-   Link Discord user to Jellyseerr/Jellyfin user.
-   View current requests and their status.

## Running with Docker Compose (Recommended)

Using Docker Compose is the recommended way to run JellyRequest. It simplifies the management of the bot's container and its configuration.

### Prerequisites

-   Docker and Docker Compose installed and running.
-   A Discord Bot Token.
-   Access to a Jellyseerr instance (URL and API Key).
-   Access to a Jellyfin instance (URL and API Key).

### 1. Create `docker-compose.yml`

Create a file named `docker-compose.yml` in a directory of your choice with the following content:

```yaml
services:
  jellyrequest:
    build: https://github.com/mvanhare/jellyrequest.git
    container_name: jellyrequest
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./data:/app/data
```

### 2. Create an `.env` file

In the same directory as your `docker-compose.yml` file, create a file named `.env`. This file will store your configuration variables.

**Example `.env` file:**

```env
# Discord Bot Configuration
DISCORD_BOT_TOKEN=DISCORD_BOT_TOKEN
# Jellyseerr Configuration
JELLYSEERR_URL=JELLYSEERR_URL
JELLYSEERR_API_KEY=JELLYSEERR_API_KEY

# Jellyfin Configuration
JELLYFIN_URL=JELLYFIN_URL
JELLYFIN_API_KEY=JELLYFIN_API_KEY

# Optional: Timezone for container logs (e.g., America/New_York, Europe/London)
TZ=America/New_York
```

Replace the placeholder values (e.g., `DISCORD_BOT_TOKEN`, `JELLYSEERR_URL`) with your actual credentials and URLs.

### 3. Obtaining API Keys and URLs

*   **Discord Bot Token (`DISCORD_BOT_TOKEN`)**:
    1.  Go to the [Discord Developer Portal](https://discord.com/developers/applications).
    2.  Click "New Application" and give your bot a name.
    3.  Navigate to the "Bot" tab.
    4.  Click "Add Bot" and confirm.
    5.  Under the "Token" section, click "Copy" to get your bot token.
        *   **Important**: You will also need to enable "Message Content Intent" under "Privileged Gateway Intents" on this page for the bot to read messages.
    6.  To invite your bot to a server, go to the "OAuth2" -> "URL Generator" tab. Select the `bot` scope and then choose the necessary permissions (e.g., `Send Messages`, `Read Message History`, `Embed Links`). Copy the generated URL and open it in your browser to add the bot to your server.

*   **Jellyseerr URL (`JELLYSEERR_URL`)**:
    *   This is the main URL you use to access your Jellyseerr instance (e.g., `http://localhost:5055` or `https://requests.yourdomain.com`).

*   **Jellyseerr API Key (`JELLYSEERR_API_KEY`)**:
    1.  Open your Jellyseerr instance.
    2.  Go to Settings -> General.
    3.  The API Key is listed there. Copy it.

*   **Jellyfin URL (`JELLYFIN_URL`)**:
    *   This is the main URL you use to access your Jellyfin instance (e.g., `http://localhost:8096` or `https://media.yourdomain.com`).

*   **Jellyfin API Key (`JELLYFIN_API_KEY`)**:
    1.  Open your Jellyfin instance.
    2.  Go to Dashboard -> API Keys (under the Advanced section in the sidebar).
    3.  Click the "+" button to generate a new API key.
    4.  Give it an optional name (e.g., "JellyRequest Bot") and click Save.
    5.  Copy the generated API key.

### 4. Create a `data` directory

The `docker-compose.yml` is configured to map a local `./data` directory to `/app/data` inside the container. This is where the `linked_users.db` file will be stored to persist user links.

```bash
mkdir data
```

### 5. Build and Start the Bot

Navigate to the directory containing your `docker-compose.yml` and `.env` files, then run:

```bash
docker-compose up -d --build
```

This command will:
- Pull the latest code from the GitHub repository specified in `build`.
- Build the Docker image.
- Create and start the container in detached mode (`-d`).
- Load environment variables from your `.env` file.
- Mount the `./data` directory for database persistence.
- Automatically restart the bot if it crashes (due to `restart: unless-stopped`).

### 6. Viewing Logs

To view the bot's logs:

```bash
docker-compose logs -f jellyrequest
```

### 7. Stopping the Bot

To stop and remove the bot's container:

```bash
docker-compose down
```
The `data` directory (and the `linked_users.db` within) will remain on your host.

## Development

(TODO: Add instructions for local development if needed, e.g., setting up a virtual environment, installing dependencies from `requirements.txt`, and running `python jellyrequest.py` directly with environment variables set locally.)

## Contributing

(TODO: Add guidelines for contributing if this were an open project.)
```
