import sqlite3
import discord
from discord.ui import View, Button, button
import requests # Added for create_request_embed
import os # For creating data directory

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500" # Base URL for TMDb poster images.

DB_PATH = "data/linked_users.db"

# --- Database Functions ---
def init_db():
    """Initializes the SQLite database and creates the linked_users table if it doesn't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS linked_users (
            discord_id TEXT PRIMARY KEY,
            jellyseerr_user_id TEXT,
            jellyfin_user_id TEXT,
            username TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME
        )
    ''')
    # Add expires_at column if it doesn't exist for backward compatibility
    try:
        cursor.execute('ALTER TABLE linked_users ADD COLUMN expires_at DATETIME')
    except sqlite3.OperationalError:
        pass # Column already exists
    try:
        cursor.execute('ALTER TABLE linked_users ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP')
    except sqlite3.OperationalError:
        pass # Column already exists
    # Add guild_id and role_name for role management on expiration
    try:
        cursor.execute('ALTER TABLE linked_users ADD COLUMN guild_id TEXT')
    except sqlite3.OperationalError:
        pass # Column already exists
    try:
        cursor.execute('ALTER TABLE linked_users ADD COLUMN role_name TEXT')
    except sqlite3.OperationalError:
        pass # Column already exists
    conn.commit()
    conn.close()

def delete_linked_user(discord_id: str):
    """Deletes a linked user from the database by their Discord ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM linked_users WHERE discord_id=?', (discord_id,))
    conn.commit()
    conn.close()

def store_linked_user(discord_id, jellyseerr_user_id, jellyfin_user_id, username=None, expires_at=None, guild_id=None, role_name=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO linked_users (discord_id, jellyseerr_user_id, jellyfin_user_id, username, expires_at, guild_id, role_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(discord_id) DO UPDATE SET
            jellyseerr_user_id=excluded.jellyseerr_user_id,
            jellyfin_user_id=excluded.jellyfin_user_id,
            username=excluded.username,
            expires_at=excluded.expires_at,
            guild_id=excluded.guild_id,
            role_name=excluded.role_name
    ''', (str(discord_id), jellyseerr_user_id, jellyfin_user_id, username, expires_at, guild_id, role_name))
    conn.commit()
    conn.close()

def get_linked_user(discord_id: str):
    """Retrieves a linked user's details from the database by their Discord ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Also retrieve expires_at
    cursor.execute('''
        SELECT jellyseerr_user_id, jellyfin_user_id, username, expires_at
        FROM linked_users WHERE discord_id=?
    ''', (str(discord_id),))
    result = cursor.fetchone()
    conn.close()
    return result

def get_all_expiring_users():
    """Retrieves all users with an expiration date."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT discord_id, jellyfin_user_id, expires_at, guild_id, role_name FROM linked_users WHERE expires_at IS NOT NULL')
    results = cursor.fetchall()
    conn.close()
    return results

# --- Embed Creation Helpers ---
def create_embed_for_item(item: dict, current_index: int, total_results: int) -> discord.Embed:
    """Creates a Discord embed for a media item (movie or TV show)."""
    title = item.get("title") or item.get("name") or "Unknown Title"
    year_str = item.get("releaseDate") or item.get("firstAirDate", "N/A")
    year = year_str.split("-")[0] if isinstance(year_str, str) else "N/A"

    media_type = item.get("mediaType", "N/A").capitalize()
    overview = item.get("overview", "No overview available.")

    embed = discord.Embed(
        title=f"{title} ({year})",
        description=overview,
        color=discord.Color.blue()
    )
    embed.add_field(name="Type", value=media_type, inline=True)

    poster_path = item.get("posterPath")
    if poster_path:
        embed.set_thumbnail(url=f"{TMDB_IMAGE_BASE_URL}{poster_path}")

    embed.set_footer(text=f"Result {current_index + 1} of {total_results}")
    return embed

# --- Jellyseerr Request Status Helper Functions ---
def get_status_emoji(status_id):
    """Returns an emoji corresponding to the Jellyseerr request status."""
    return {
        1: "⏳ Pending",
        2: "✅ Approved",
        3: "⚙️ Processing",
        4: "🗂️ Partially Available",
        5: "🎬 Available"
    }.get(status_id, "❓ Unknown")

def create_request_embed(request: dict, current_index: int, total_results: int,
                         jellyseerr_url: str, jellyseerr_headers: dict) -> discord.Embed:
    """Creates a Discord embed for a media request, fetching additional details from Jellyseerr."""
    media = request.get("media", {})
    media_type = media.get("mediaType", "unknown")
    tmdb_id = media.get("tmdbId")

    if not tmdb_id:
        return discord.Embed(title="Error", description="Request is missing a TMDB ID.", color=discord.Color.red())

    try:
        endpoint = 'tv' if media_type == 'tv' else 'movie'
        media_info_url = f"{jellyseerr_url}/api/v1/{endpoint}/{tmdb_id}" # Use passed-in jellyseerr_url
        response = requests.get(media_info_url, headers=jellyseerr_headers)
        response.raise_for_status()
        media_info = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching media details from {media_info_url}: {e}") # Log URL for debugging
        return discord.Embed(title="Error", description="Could not fetch details for this request.", color=discord.Color.red())

    if media_type == 'tv':
        title = media_info.get("name", "Unknown Title")
        date_str = media_info.get("firstAirDate", "")
    else: # Default to movie
        title = media_info.get("title", "Unknown Title")
        date_str = media_info.get("releaseDate", "")

    year = date_str.split('-')[0] if date_str else "Unknown Year"

    status = get_status_emoji(request.get("status"))
    requested_date = request.get("createdAt", "N/A").split('T')[0]
    poster_path = media_info.get("posterPath")

    embed = discord.Embed(
        title=f"{title} ({year})",
        description=f"Status of your request.",
        color=discord.Color.green()
    )

    if poster_path:
        embed.set_thumbnail(url=f"{TMDB_IMAGE_BASE_URL}{poster_path}")

    embed.add_field(name="Type", value=media_type.capitalize(), inline=True)
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Requested On", value=requested_date, inline=False)

    embed.set_footer(text=f"Request {current_index + 1} of {total_results}")
    return embed

# --- Pagination Views ---
class PaginationView(View):
    """A view for paginating through search results, allowing users to request media."""
    def __init__(self, results: list, jellyseerr_url: str, jellyseerr_headers: dict):
        super().__init__(timeout=300)
        self.results = results
        self.current_index = 0
        self.total_results = len(results)
        self.jellyseerr_url = jellyseerr_url
        self.jellyseerr_headers = jellyseerr_headers
        self.update_button_state()

    def update_button_state(self):
        """Disables/enables previous/next buttons based on the current index."""
        # Assumes buttons are: Previous, Request, Next in self.children
        if len(self.children) == 3:
            prev_button = self.children[0]
            next_button = self.children[2]
            prev_button.disabled = self.current_index == 0
            next_button.disabled = self.current_index >= self.total_results - 1


    @button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, custom_id="previous_media")
    async def previous_button(self, interaction: discord.Interaction, button_obj: discord.ui.Button):
        await interaction.response.defer()
        if self.current_index > 0:
            self.current_index -= 1
            self.update_button_state()
            embed = create_embed_for_item(self.results[self.current_index], self.current_index, self.total_results)
            await interaction.edit_original_response(embed=embed, view=self)
        # If already at the first item, the defer() handles the interaction acknowledgment.

    @button(label="Request", style=discord.ButtonStyle.success, custom_id="request_media")
    async def request_button(self, interaction: discord.Interaction, button_obj: discord.ui.Button):
        item = self.results[self.current_index]
        media_type = item.get("mediaType")
        tmdb_id = item.get("id")

        linked_user_data = get_linked_user(str(interaction.user.id))

        if not linked_user_data or not linked_user_data[0]: # Jellyseerr User ID is the first element
            await interaction.response.send_message("⚠️ You need to link your Discord account to a Jellyseerr user first using `/link`.", ephemeral=True)
            return

        jellyseerr_user_id = int(linked_user_data[0])
        request_url = f"{self.jellyseerr_url}/api/v1/request"
        payload = {
            "mediaType": media_type,
            "mediaId": tmdb_id,
            "userId": jellyseerr_user_id,
        }

        if media_type == 'tv':
            payload['seasons'] = 'all'

        await interaction.response.defer(ephemeral=True)

        try:
            response = requests.post(request_url, headers=self.jellyseerr_headers, json=payload)
            response.raise_for_status()
            title = item.get("title") or item.get("name", "the selected item")
            await interaction.followup.send(f"✅ Successfully requested '{title}'!", ephemeral=True)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                await interaction.followup.send("⚠️ This item is already available or has been requested.", ephemeral=True)
            else:
                error_details = "Could not parse error from Jellyseerr."
                try:
                    error_details = e.response.json().get('message', e.response.text)
                except requests.exceptions.JSONDecodeError:
                    error_details = e.response.text
                await interaction.followup.send(f"❌ An error occurred: {e.response.status_code} - {error_details}", ephemeral=True)
                print(f"Error requesting item: {e.response.text}")
        except requests.exceptions.RequestException as e:
            await interaction.followup.send(f"❌ A network error occurred: {e}", ephemeral=True)

    @button(label="Next ➡️", style=discord.ButtonStyle.secondary, custom_id="next_media")
    async def next_button(self, interaction: discord.Interaction, button_obj: discord.ui.Button):
        await interaction.response.defer()
        if self.current_index < self.total_results - 1:
            self.current_index += 1
            self.update_button_state()
            embed = create_embed_for_item(self.results[self.current_index], self.current_index, self.total_results)
            await interaction.edit_original_response(embed=embed, view=self)
        # If already at the last item, the defer() handles the interaction acknowledgment.


class RequestsPaginationView(View):
    """A view for paginating through a user's media requests."""
    def __init__(self, requests_data: list, jellyseerr_url: str, jellyseerr_headers: dict):
        super().__init__(timeout=300)
        self.requests_data = requests_data
        self.current_index = 0
        self.total_results = len(requests_data)
        self.jellyseerr_url = jellyseerr_url
        self.jellyseerr_headers = jellyseerr_headers
        self.update_button_state()

    def update_button_state(self):
        """Disables/enables previous/next buttons based on the current index."""
        # Assumes buttons are: Previous, Next in self.children
        if len(self.children) >= 2:
            prev_button = self.children[0]
            next_button = self.children[1]
            prev_button.disabled = self.current_index == 0
            next_button.disabled = self.current_index >= self.total_results - 1

    @button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, custom_id="previous_request_status")
    async def previous_button(self, interaction: discord.Interaction, button_obj: discord.ui.Button):
        await interaction.response.defer()
        if self.current_index > 0:
            self.current_index -= 1
            self.update_button_state()
            embed = create_request_embed(
                self.requests_data[self.current_index],
                self.current_index,
                self.total_results,
                self.jellyseerr_url,
                self.jellyseerr_headers
            )
            await interaction.edit_original_response(embed=embed, view=self)

    @button(label="Next ➡️", style=discord.ButtonStyle.secondary, custom_id="next_request_status")
    async def next_button(self, interaction: discord.Interaction, button_obj: discord.ui.Button):
        await interaction.response.defer()
        if self.current_index < self.total_results - 1:
            self.current_index += 1
            self.update_button_state()
            embed = create_request_embed(
                self.requests_data[self.current_index],
                self.current_index,
                self.total_results,
                self.jellyseerr_url,
                self.jellyseerr_headers
            )
            await interaction.edit_original_response(embed=embed, view=self)

# End of utils.py
