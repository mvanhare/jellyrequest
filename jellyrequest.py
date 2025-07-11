import secrets
import discord
from discord.ext import commands
from discord.ui import View, Button, button
from urllib.parse import urlencode, quote
import requests
import json
import re
import sqlite3

# --- Configuration ---
JELLYSEERR_URL = "https://requests.demonbox.co"  # Replace with your Jellyseerr URL
JELLYSEERR_API_KEY = "MTc1MTI3MTE1NzE3OTNhZjRmYjMxLTEzYWUtNGMyNi04ZDMwLWIzNzNiMTI3MGY2OA=="  # Replace with your Jellyseerr API key
DISCORD_BOT_TOKEN = "MTM5MzAwMDIxNjk2OTM1MTI1OA.Gwj_r5.wjr8Tg3YHG0_n6liXbHk1aTtKZgb61MEAP2qwU"  # Replace with your Discord bot token
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"  # TMDb image URL
# ---------------------
JELLYFIN_URL = "https://tv.demonbox.co" # 🔑 Replace with your Jellyfin URL
JELLYFIN_API_KEY = "6b97626e804b4331b8dec89bfa3e9c10"   # 🔑 Replace with your Jellyfin API Key
# ---------------------

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

jellyseerr_headers = {
    "X-Api-Key": JELLYSEERR_API_KEY,
    "Content-Type": "application/json"
}
jellyfin_headers = {
    "X-Emby-Token": JELLYFIN_API_KEY, # Jellyfin uses X-Emby-Token header
    "Content-Type": "application/json"
}

def init_db():
    conn = sqlite3.connect("linked_users.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS linked_users (
            discord_id TEXT PRIMARY KEY,
            jellyseerr_user_id TEXT,
            jellyfin_user_id TEXT,
            username TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def delete_linked_user(discord_id):
    """Delete a linked user from the database."""
    conn = sqlite3.connect("linked_users.db")
    cursor = conn.cursor()
    cursor.execute('DELETE FROM linked_users WHERE discord_id=?', (str(discord_id),))
    conn.commit()
    conn.close()

def store_linked_user(discord_id, jellyseerr_user_id, jellyfin_user_id, username=None):
    conn = sqlite3.connect("linked_users.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO linked_users (discord_id, jellyseerr_user_id, jellyfin_user_id, username)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(discord_id) DO UPDATE SET
            jellyseerr_user_id=excluded.jellyseerr_user_id,
            jellyfin_user_id=excluded.jellyfin_user_id,
            username=excluded.username
    ''', (str(discord_id), jellyseerr_user_id, jellyfin_user_id, username))
    conn.commit()
    conn.close()

def get_linked_user(discord_id):
    conn = sqlite3.connect("linked_users.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT jellyseerr_user_id, jellyfin_user_id, username
        FROM linked_users WHERE discord_id=?
    ''', (str(discord_id),))
    result = cursor.fetchone()
    conn.close()
    return result  # returns (jellyseerr_id, jellyfin_id, username) or None


def create_embed_for_item(item, current_index, total_results):
    """Helper function to create a Discord embed for a media item."""
    title = item.get("title", None) or item.get("name", None) # Use 'title' for movies, 'name' for TV shows
    if not title:
        title = "Unknown Title"
    year_str = item.get("releaseDate", item.get("firstAirDate", "N/A"))
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

class PaginationView(View):
    def __init__(self, results):
        super().__init__(timeout=300)
        self.results = results
        self.current_index = 0
        self.total_results = len(results)
        self.update_button_state()

    def update_button_state(self):
        """Disables/enables previous/next buttons based on current index."""
        if len(self.children) == 3:
            self.children[0].disabled = self.current_index == 0
            self.children[2].disabled = self.current_index >= self.total_results - 1

    @button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, custom_id="previous")
    # CORRECT SIGNATURE: interaction is the first parameter, button is the second.
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await button.response.defer()
        if self.current_index > 0:
            self.current_index -= 1
            self.update_button_state()
            embed = create_embed_for_item(self.results[self.current_index], self.current_index, self.total_results)
            await button.edit_original_response(embed=embed, view=self)

    @button(label="Request", style=discord.ButtonStyle.success, custom_id="request")
    async def request_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        item = self.results[self.current_index]
        media_type = item.get("mediaType")
        tmdb_id = item.get("id")
        jellyseerr_user_id = int(get_linked_user(button.user.id)[0])

        if not jellyseerr_user_id:
            await button.response.send_message("⚠️ You need to link your Discord account to a Jellyseerr user first using `/link`.", ephemeral=True)
            return

        request_url = f"{JELLYSEERR_URL}/api/v1/request"

        payload = {
            "mediaType": media_type,
            "mediaId": tmdb_id,
            "userId": jellyseerr_user_id,  # Use the linked Jellyseerr user ID
        }
        
        # If it's a TV show and you want to explicitly request all seasons, you can do this:
        if media_type == 'tv':
            payload['seasons'] = 'all' # Or pass an array of season numbers [1, 2, 3]

        # --- END OF CORRECTION ---

        await button.response.defer(ephemeral=True)

        try:
            # Use `json` parameter in requests library to automatically handle serialization and headers
            response = requests.post(request_url, headers=jellyseerr_headers, json=payload)
            response.raise_for_status()

            # Using interaction.followup.send since we deferred the response
            title = item.get("title") or item.get("name", "the selected item")
            await button.followup.send(f"✅ Successfully requested '{title}'!", ephemeral=True)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409: # Conflict
                await button.followup.send("⚠️ This item is already available or has been requested.", ephemeral=True)
            else:
                error_details = e.response.json().get('message', e.response.text)
                await button.followup.send(f"❌ An error occurred: {e.response.status_code} - {error_details}", ephemeral=True)
                print(f"Error requesting item: {e.response.text}")
        except requests.exceptions.RequestException as e:
            await button.followup.send(f"❌ A network error occurred: {e}", ephemeral=True)

    @button(label="Next ➡️", style=discord.ButtonStyle.secondary, custom_id="next")
    # CORRECT SIGNATURE: interaction is the first parameter, button is the second.
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await button.response.defer()
        if self.current_index < self.total_results - 1:
            self.current_index += 1
            self.update_button_state()
            embed = create_embed_for_item(self.results[self.current_index], self.current_index, self.total_results)
            await button.edit_original_response(embed=embed, view=self)

# --------------------------------------------
# Jellyseerr Request Status Helper Functions
# --------------------------------------------

def get_status_emoji(status_id):
    """Returns an emoji corresponding to the Jellyseerr request status."""
    return {
        1: "⏳ Pending",
        2: "✅ Approved",
        3: "⚙️ Processing",
        4: "🗂️ Partially Available",
        5: "🎬 Available"
    }.get(status_id, "❓ Unknown")

def create_request_embed(request, current_index, total_results):
    """Helper function to create a Discord embed for a media request."""
    # This is the base information from the request list
    media = request.get("media", {})
    media_type = media.get("mediaType", "unknown")
    tmdb_id = media.get("tmdbId")
    
    # Fetch detailed media information using the tmdbId
    if not tmdb_id:
        return discord.Embed(title="Error", description="Request is missing a TMDB ID.", color=discord.Color.red())

    try:
        endpoint = 'tv' if media_type == 'tv' else 'movie'
        media_info_url = f"{JELLYSEERR_URL}/api/v1/{endpoint}/{tmdb_id}"
        response = requests.get(media_info_url, headers=jellyseerr_headers)
        response.raise_for_status()
        media_info = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching media details: {e}")
        return discord.Embed(title="Error", description="Could not fetch details for this request.", color=discord.Color.red())

    # --- FIX ---
    # Correctly extract title and year from the detailed media_info
    if media_type == 'tv':
        title = media_info.get("name", "Unknown Title")
        date_str = media_info.get("firstAirDate", "")
    else: # Default to movie
        title = media_info.get("title", "Unknown Title")
        date_str = media_info.get("releaseDate", "")

    # Safely extract year from the date string (e.g., "2023-10-25")
    year = date_str.split('-')[0] if date_str else "Unknown Year"
    # --- END OF FIX ---
    
    status = get_status_emoji(request.get("status"))
    requested_date = request.get("createdAt", "N/A").split('T')[0] # Format date to YYYY-MM-DD
    poster_path = media_info.get("posterPath")

    # Create the embed with the corrected information
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


class RequestsPaginationView(View):
    def __init__(self, requests):
        super().__init__(timeout=300)
        self.requests = requests
        self.current_index = 0
        self.total_results = len(requests)
        self.update_button_state()

    def update_button_state(self):
        """Disables/enables previous/next buttons based on current index."""
        # Ensure children have been added before trying to access them
        if len(self.children) >= 2:
            self.children[0].disabled = self.current_index == 0
            self.children[1].disabled = self.current_index >= self.total_results - 1

    @button(label="⬅️ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await button.response.defer()
        if self.current_index > 0:
            self.current_index -= 1
            self.update_button_state()
            embed = create_request_embed(self.requests[self.current_index], self.current_index, self.total_results)
            await button.edit_original_response(embed=embed, view=self)

    @button(label="Next ➡️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await button.response.defer()
        if self.current_index < self.total_results - 1:
            self.current_index += 1
            self.update_button_state()
            embed = create_request_embed(self.requests[self.current_index], self.current_index, self.total_results)
            await button.edit_original_response(embed=embed, view=self)

# --- Bot Events and Commands ---

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    print("Bot is ready to receive commands.")

@bot.slash_command(name="request", description="Search for a movie or TV show")
async def request(ctx, query: str):
    """Searches for media on Jellyseerr and displays results with pagination."""
    await ctx.defer() 

    search_url = f"{JELLYSEERR_URL}/api/v1/search"
    params = urlencode({"query": query}, quote_via=quote)
    full_url = f"{search_url}?{params}"
    
    try:
        response = requests.get(full_url, headers=jellyseerr_headers)
        response.raise_for_status()
        results = response.json().get("results", [])
        print(f"Search results for '{query}': {results}")  # Debugging line to see the results

        if not results:
            await ctx.followup.send("No results found for your query.")
            return

        initial_embed = create_embed_for_item(results[0], 0, len(results))
        view = PaginationView(results)
        
        await ctx.followup.send(embed=initial_embed, view=view)

    except requests.exceptions.RequestException as e:
        await ctx.followup.send(f"An error occurred while searching: {e}")

# DISCOVER COMMAND
@bot.slash_command(name="discover", description="Discover new movies or TV shows")
async def discover(ctx):
    await ctx.defer()
    try:
        movie_response = requests.get(f"{JELLYSEERR_URL}/api/v1/discover/movies", headers=jellyseerr_headers)
        tv_response = requests.get(f"{JELLYSEERR_URL}/api/v1/discover/tv", headers=jellyseerr_headers)

        movie_response.raise_for_status()
        tv_response.raise_for_status()
        
        movies = movie_response.json().get("results", [])
        tv_shows = tv_response.json().get("results", [])
        popular_items = movies + tv_shows
        if not popular_items:
            await ctx.followup.send("No popular items found.")
            return
        
        initial_embed = create_embed_for_item(popular_items[0], 0, len(popular_items))
        view = PaginationView(popular_items)
        await ctx.followup.send(embed=initial_embed, view=view)
    except requests.exceptions.RequestException as e:
        await ctx.followup.send(f"An error occurred while fetching popular items: {e}")

# INVITE COMMAND (robust and fixed)
@bot.slash_command(name="invite", description="Adds a user to Jellyseerr and Jellyfin.")
@commands.has_permissions(administrator=True)
async def invite(ctx, user: discord.Member):
    await ctx.defer(ephemeral=True)
    username = re.sub(r"[^a-zA-Z0-9.-]", "", user.name)
    temp_password = secrets.token_urlsafe(12)

    # Step 1: Create Jellyfin User
    try:
        jellyfin_user_payload = {
            "Name": username,
            "Password": temp_password,
            "Policy": {
                "IsAdministrator": False,
                "EnableUserPreferenceAccess": True,
                "EnableMediaPlayback": True,
                "EnableLiveTvAccess": False,
                "EnableLiveTvManagement": False,

            }
        }
        response_fin = requests.post(f"{JELLYFIN_URL}/Users/New", headers=jellyfin_headers, json=jellyfin_user_payload)
        if "User with the same name already exists" in response_fin.text:
            await ctx.followup.send(f"⚠️ User '{username}' already exists in Jellyfin. Cannot proceed.")
            return
        response_fin.raise_for_status()
        jellyfin_user_id = response_fin.json().get("Id")
        if not jellyfin_user_id:
            await ctx.followup.send("❌ Failed to get user ID from Jellyfin response.")
            return
    except requests.exceptions.RequestException as e:
        await ctx.followup.send(f"❌ Failed to create Jellyfin user: {e.response.text if e.response else e}")
        return

    # Step 2: Import User to Jellyseerr
    jellyseerr_user = None
    try:
        response_seerr_import = requests.post(
            f"{JELLYSEERR_URL}/api/v1/user/import-from-jellyfin",
            headers=jellyseerr_headers,
            json={"jellyfinUserIds": [jellyfin_user_id]}
        )
        response_seerr_import.raise_for_status()
        created_users = response_seerr_import.json()
        if not created_users:
            await ctx.followup.send("❌ User created in Jellyfin but import to Jellyseerr failed.")
            return
        jellyseerr_user = created_users[0]
    except requests.exceptions.RequestException as e:
        await ctx.followup.send(f"❌ Failed to import Jellyfin user to Jellyseerr: {e.response.text if e.response else e}")
        return

    # Step 3: Set Discord ID on the new Jellyseerr User
    store_linked_user(
    discord_id=user.id,
    jellyseerr_user_id=jellyseerr_user.get("id"),
    jellyfin_user_id=jellyfin_user_id,
    username=username
    )

    # Step 4: DM Credentials to User
    try:
        dm_message = (
            f"## Welcome to the Media Server! 🎉\n\n"
            f"An account has been created for you. Here are your login details:\n\n"
            f"**Username:** `{username}`\n"
            f"**Temporary Password:** `{temp_password}`\n\n"
            f"Please change your password after logging in.\n\n"
            f"🔗 Jellyfin: {JELLYFIN_URL}\n"
            f"🔗 Jellyseerr: {JELLYSEERR_URL}"
        )
        await user.send(dm_message)
    except discord.Forbidden:
        await ctx.followup.send(f"✅ Accounts created for {username}, but I could not DM them. Please send their password manually: `{temp_password}`")
        return
    except Exception as e:
        await ctx.followup.send(f"✅ Accounts created, but failed to DM. Please send password manually: `{temp_password}`. Error: {e}")
        return

    # Step 5: Confirm Success
    await ctx.followup.send(f"✅ Successfully created accounts for `{username}` and sent them a DM with credentials.")

# LINK COMMAND (robust and fixes discordId update)
# LINK COMMAND (robust and fixes discordId update)
@bot.slash_command(name="link", description="Link your Discord account to Jellyseerr user")
async def link(ctx, jellyfin_username: str, password: str):
    await ctx.defer(ephemeral=True) # Use ephemeral to hide password command

    # Step 1: Authenticate with Jellyfin to verify the password
    auth_payload = {
        "Username": jellyfin_username,
        "Pw": password
    }
    jellyfin_user_data = None
    try:
        auth_response = requests.post(
            f"{JELLYFIN_URL}/Users/AuthenticateByName",
            json=auth_payload,
            # No API key needed for this public endpoint
            headers= jellyfin_headers,
            timeout=10
        )
        
        # Check for authentication failure (401 Unauthorized)
        if auth_response.status_code == 401:
            await ctx.followup.send("❌ **Authentication Failed:** Invalid Jellyfin username or password.")
            return

        auth_response.raise_for_status()  # Raise an exception for other HTTP errors
        jellyfin_user_data = auth_response.json()
        jellyfin_user_id = jellyfin_user_data.get("User", {}).get("Id")

        if not jellyfin_user_id:
            await ctx.followup.send("❌ **Error:** Could not retrieve Jellyfin User ID after authentication.")
            return

    except requests.exceptions.RequestException as e:
        await ctx.followup.send(f"❌ An error occurred while trying to authenticate with Jellyfin: {e}")
        return

    # Step 2: Find the corresponding Jellyseerr user
    try:
        seerr_response = requests.get(f"{JELLYSEERR_URL}/api/v1/user", headers=jellyseerr_headers, timeout=10)
        seerr_response.raise_for_status()
        seerr_users = seerr_response.json().get("results", [])
    except requests.exceptions.RequestException as e:
        await ctx.followup.send(f"❌ Failed to fetch users from Jellyseerr: {e}")
        return

    # Find Jellyseerr user by matching the now-verified Jellyfin User ID
    jellyseerr_user = next(
        (u for u in seerr_users if u.get("jellyfinUserId") == jellyfin_user_id),
        None
    )

    if not jellyseerr_user:
        await ctx.followup.send(
            f"⚠️ **Account Not Found in Jellyseerr.** Although your Jellyfin login is correct, "
            f"your account ('{jellyfin_username}') has not been imported into Jellyseerr. Please contact an administrator."
        )
        return

    # Step 3: Store the linked user in the database
    store_linked_user(
        discord_id=ctx.author.id,
        jellyseerr_user_id=jellyseerr_user.get("id"),
        jellyfin_user_id=jellyfin_user_id,
        username=jellyseerr_user.get("jellyfinUsername")
    )

    await ctx.followup.send(f"✅ **Success!** Your Discord account is now linked to the Jellyfin/Jellyseerr user '{jellyfin_username}'.")

# UNLINK COMMAND
@bot.slash_command(name="unlink", description="Unlink your Discord account from Jellyseerr")
async def unlink(ctx):
    await ctx.defer()
    linked_user = get_linked_user(ctx.author.id)
    if not linked_user:
        await ctx.followup.send("⚠️ You haven't linked your account yet.")
        return
    
    # Delete the linked user from the database
    delete_linked_user(ctx.author.id)
    await ctx.followup.send("✅ Unlinked your Discord account from Jellyseerr successfully.")

# WATCH COMMAND (fixed Discord ID lookup inside settings.discordId)
@bot.slash_command(name="watch", description="Get your watch statistics")
async def watch(ctx):
    await ctx.defer()

    linked_user = get_linked_user(ctx.author.id)
    if not linked_user:
        await ctx.followup.send("⚠️ You haven't linked your account yet. Use `/link` to get started.")
        return

    _, jellyfin_user_id, username = linked_user
    if not jellyfin_user_id:
        await ctx.followup.send("⚠️ Your Jellyfin account is not linked.")
        return

    # Query Jellyfin watch data
    params = {
        "Recursive": "true",
        "IncludeItemTypes": "Movie,Episode",
        "Filters": "IsPlayed",
        "Fields": "RunTimeTicks,UserData,SeriesName"
    }

    try:
        response = requests.get(
            f"{JELLYFIN_URL}/Users/{jellyfin_user_id}/Items",
            headers=jellyfin_headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        items = response.json().get("Items", [])
    except Exception as e:
        await ctx.followup.send(f"Failed to fetch watch data from Jellyfin: {e}")
        return

    watched_count = len(items)
    total_ticks = sum(item.get("RunTimeTicks", 0) for item in items)
    total_seconds = total_ticks / 10_000_000
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    last_watched = max(items, key=lambda x: x.get("UserData", {}).get("LastPlayedDate", ""), default=None)

    embed = discord.Embed(
        title=f"📊 {ctx.author.name}'s Watch Statistics",
        color=discord.Color.blue()
    )
    embed.add_field(name="📺 Total Watched Items", value=str(watched_count), inline=False)
    embed.add_field(name="⏱️ Total Watch Time", value=f"{int(days)}d {int(hours)}h {int(minutes)}m", inline=False)

    if last_watched:
        title = last_watched.get("Name", "Unknown")
        if last_watched.get("Type") == "Episode" and last_watched.get("SeriesName"):
            title = f"{last_watched.get('SeriesName')} - {title}"
        embed.add_field(name="👀 Last Watched", value=title, inline=False)

    await ctx.followup.send(embed=embed)

@bot.slash_command(name="requests", description="View the status of your media requests")
async def my_requests(ctx):
    """Displays a paginated list of the user's media requests from Jellyseerr."""
    await ctx.defer(ephemeral=True) # Use ephemeral so only the user sees their requests

    linked_user = get_linked_user(ctx.author.id)
    if not linked_user or not linked_user[0]: # Check for linked user and jellyseerr_id
        await ctx.followup.send("⚠️ You need to link your account first using `/link`.", ephemeral=True)
        return

    jellyseerr_user_id = linked_user[0]

    # --- API Call to Jellyseerr to get requests ---
    try:
        # We filter requests by the user's Jellyseerr ID
        params = {
            "take": 100, # Get up to 100 requests
            "skip": 0,
            "sort": "added",
            "filter": "all",
            "requestedBy": jellyseerr_user_id
        }
        
        response = requests.get(
            f"{JELLYSEERR_URL}/api/v1/request",
            headers=jellyseerr_headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        user_requests = response.json().get("results", [])

    except requests.exceptions.RequestException as e:
        await ctx.followup.send(f"❌ An error occurred while fetching your requests: {e}", ephemeral=True)
        return

    # --- Displaying the results ---
    if not user_requests:
        await ctx.followup.send("You have no pending or completed requests.", ephemeral=True)
        return
    
    # Sort requests so newest appear first
    user_requests.sort(key=lambda r: r['createdAt'], reverse=True)

    initial_embed = create_request_embed(user_requests[0], 0, len(user_requests))
    view = RequestsPaginationView(user_requests)
    
    await ctx.followup.send(embed=initial_embed, view=view, ephemeral=True)

# Run the bot
bot.run(DISCORD_BOT_TOKEN)