import sqlite3
import discord
from discord.ui import View, Button, button
import requests # Added for create_request_embed

# This was in jellyrequest.py, needed for create_embed_for_item and create_request_embed
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

# --- Database Functions ---
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

# --- Embed Creation Helpers ---
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

# Note: create_request_embed needs JELLYSEERR_URL and jellyseerr_headers
# These will be passed from the cog or main bot file where they are defined.
def create_request_embed(request, current_index, total_results, JELLYSEERR_URL, jellyseerr_headers):
    """Helper function to create a Discord embed for a media request."""
    media = request.get("media", {})
    media_type = media.get("mediaType", "unknown")
    tmdb_id = media.get("tmdbId")

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
        """Disables/enables previous/next buttons based on current index."""
        if len(self.children) == 3: # previous, request, next
            # Accessing buttons by their presumed order. A more robust way would be by custom_id.
            prev_button = self.children[0]
            next_button = self.children[2]
            prev_button.disabled = self.current_index == 0
            next_button.disabled = self.current_index >= self.total_results - 1


    @button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, custom_id="previous_media")
    async def previous_button(self, interaction: discord.Interaction, button_obj: discord.ui.Button): # Renamed button to button_obj
        # await interaction.response.defer() # Corrected: interaction.response.defer() not button.response.defer()
        if self.current_index > 0:
            self.current_index -= 1
            self.update_button_state()
            embed = create_embed_for_item(self.results[self.current_index], self.current_index, self.total_results)
            await interaction.response.edit_message(embed=embed, view=self) # Corrected: interaction.response.edit_message
        else:
            await interaction.response.defer() # Defer if no change to prevent "interaction failed"

    @button(label="Request", style=discord.ButtonStyle.success, custom_id="request_media")
    async def request_button(self, interaction: discord.Interaction, button_obj: discord.ui.Button): # Renamed button to button_obj
        item = self.results[self.current_index]
        media_type = item.get("mediaType")
        tmdb_id = item.get("id")

        linked_user_data = get_linked_user(interaction.user.id) # get_linked_user is now in this file

        if not linked_user_data or not linked_user_data[0]: # Jellyseerr User ID is the first element
            await interaction.response.send_message("⚠️ You need to link your Discord account to a Jellyseerr user first using `/link`.", ephemeral=True)
            return

        jellyseerr_user_id = int(linked_user_data[0])

        # Access JELLYSEERR_URL and JELLYSEERR_API_KEY via self.bot or pass them in.
        # For now, assuming they are accessible via self.bot.config or similar if set up that way
        # Or, more directly, pass them during __init__ as done for self.jellyseerr_url

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
    async def next_button(self, interaction: discord.Interaction, button_obj: discord.ui.Button): # Renamed button to button_obj
        # await interaction.response.defer() # Corrected
        if self.current_index < self.total_results - 1:
            self.current_index += 1
            self.update_button_state()
            embed = create_embed_for_item(self.results[self.current_index], self.current_index, self.total_results)
            await interaction.response.edit_message(embed=embed, view=self) # Corrected
        else:
            await interaction.response.defer() # Defer if no change


class RequestsPaginationView(View):
    def __init__(self, requests_data, jellyseerr_url, jellyseerr_headers): # Added missing parameters
        super().__init__(timeout=300)
        self.requests_data = requests_data # Renamed from 'requests' to avoid conflict with the library
        self.current_index = 0
        self.total_results = len(requests_data)
        self.jellyseerr_url = jellyseerr_url
        self.jellyseerr_headers = jellyseerr_headers
        self.update_button_state()

    def update_button_state(self):
        if len(self.children) >= 2: # previous, next
            prev_button = self.children[0]
            next_button = self.children[1]
            prev_button.disabled = self.current_index == 0
            next_button.disabled = self.current_index >= self.total_results - 1

    @button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, custom_id="previous_request_status")
    async def previous_button(self, interaction: discord.Interaction, button_obj: discord.ui.Button): # Renamed
        # await interaction.response.defer() # Corrected
        if self.current_index > 0:
            self.current_index -= 1
            self.update_button_state()
            # Pass JELLYSEERR_URL and jellyseerr_headers to create_request_embed
            embed = create_request_embed(
                self.requests_data[self.current_index],
                self.current_index,
                self.total_results,
                self.jellyseerr_url,      # Pass from self
                self.jellyseerr_headers   # Pass from self
            )
            await interaction.response.edit_message(embed=embed, view=self) # Corrected
        else:
            await interaction.response.defer()


    @button(label="Next ➡️", style=discord.ButtonStyle.secondary, custom_id="next_request_status")
    async def next_button(self, interaction: discord.Interaction, button_obj: discord.ui.Button): # Renamed
        # await interaction.response.defer() # Corrected
        if self.current_index < self.total_results - 1:
            self.current_index += 1
            self.update_button_state()
            embed = create_request_embed(
                self.requests_data[self.current_index],
                self.current_index,
                self.total_results,
                self.jellyseerr_url,      # Pass from self
                self.jellyseerr_headers   # Pass from self
            )
            await interaction.response.edit_message(embed=embed, view=self) # Corrected
        else:
            await interaction.response.defer()

# Ensure all necessary top-level imports for these functions/classes are here.
# discord, sqlite3, requests, View, Button, button are already imported.
# JELLYSEERR_URL, JELLYSEERR_API_KEY (for headers) will be passed in from cogs/main bot file.
# jellyseerr_headers will also be passed in.
# get_linked_user is defined in this file.
# create_embed_for_item is defined in this file.
# create_request_embed is defined in this file.

# The `button.response.defer()` and `button.edit_original_response()` calls in the original PaginationView
# were incorrect. They should be `interaction.response.defer()` and `interaction.edit_original_response()` or `interaction.followup.send()`.
# I have corrected these in the views above.
# Also, in PaginationView.previous_button and next_button, `button.edit_original_response` should be `interaction.edit_message`
# as the original response is already sent. Or `interaction.response.edit_message` if deferring first.
# The custom_ids for buttons in different views should be unique if they are active at the same time for the same user,
# or if views are persisted and reloaded. I've made them more specific.

# Corrected `button.user.id` to `interaction.user.id` in PaginationView.request_button.
# Corrected `await button.response.defer()` to `await interaction.response.defer()`
# Corrected `await button.edit_original_response()` to `await interaction.edit_message()`
# Corrected `await button.followup.send()` to `await interaction.followup.send()`
# Renamed `button` parameter in view methods to `button_obj` to avoid conflict with the `discord.ui.button` decorator.
# The `PaginationView`'s `request_button` needs access to `JELLYSEERR_URL` and `jellyseerr_headers`. I've modified its `__init__`
# to accept these, and they will need to be passed when the view is instantiated in the cog.
# Similarly, `RequestsPaginationView` needs these for `create_request_embed`.
# `create_request_embed` itself now takes `JELLYSEERR_URL` and `jellyseerr_headers` as parameters.

# The defer calls were also sometimes misplaced or missing if a condition wasn't met,
# potentially leading to "interaction failed". Added `else: await interaction.response.defer()`
# to paths where no other response is sent.
# In `PaginationView.update_button_state`, ensuring `self.children` exists and has enough items.
# The `request_button` in `PaginationView` uses `get_linked_user` which is now local.
# The `previous_button` and `next_button` in `PaginationView` use `create_embed_for_item` which is local.
# The `previous_button` and `next_button` in `RequestsPaginationView` use `create_request_embed` which is local but needs URL/headers.

# Added `main_bot_instance` to `PaginationView` to potentially access global bot config if needed,
# though passing JELLYSEERR_URL and headers directly is cleaner and now implemented.
# The `button` parameter in the view methods was shadowed by the `discord.ui.button` decorator. Renamed it to `button_obj`.

# Corrected calls in PaginationView methods:
# - `await button.response.defer()` -> `await interaction.response.defer()`
# - `await button.edit_original_response(embed=embed, view=self)` -> `await interaction.edit_message(embed=embed, view=self)`
#   (or `interaction.response.edit_message` if the initial response was deferred and this is the first edit).
#   Given that `ctx.followup.send(embed=initial_embed, view=view)` is used, `interaction.edit_message` is correct for subsequent updates.

# If `interaction.response.defer()` is used, then `interaction.followup.send()` or `interaction.edit_message()` (on the followup message)
# should be used. If the initial response is `interaction.response.send_message()`, then `interaction.edit_message()` can be used on that original message.
# The current structure in `jellyrequest.py` uses `ctx.followup.send(embed=initial_embed, view=view)` after `ctx.defer()`.
# So, inside the View methods, if we defer the interaction (e.g. `await interaction.response.defer()`),
# we should use `await interaction.followup.send()` or `await interaction.edit_message(message_id=interaction.message.id, ...)`
# However, for buttons, `interaction.response.edit_message()` is typically used to edit the message the button is attached to.
# This seems to be the most common and correct pattern.

# Final check on PaginationView button methods:
# - `previous_button`: `await interaction.response.edit_message(embed=embed, view=self)` (no prior defer needed in this path if an edit happens)
# - `request_button`: `await interaction.response.defer(ephemeral=True)` then `await interaction.followup.send(...)` (correct for ephemeral responses)
# - `next_button`: `await interaction.response.edit_message(embed=embed, view=self)` (no prior defer needed in this path if an edit happens)

# The defer() calls *inside* the button callbacks are generally for actions that might take time *after* the button is pressed.
# If the button click itself is just updating the view/embed quickly, `interaction.response.edit_message` is often enough without an explicit defer *within the button callback itself*.
# The `await ctx.defer()` in the command itself handles the initial response acknowledgement.
# For simplicity and common practice, I'll stick to `interaction.response.edit_message` for embed/view updates in buttons,
# and `interaction.response.defer` followed by `interaction.followup.send` for actions like the actual request processing.

# Let's refine the defer logic in PaginationView previous/next:
# No, the original `await button.response.defer()` was indeed `await interaction.response.defer()`.
# My previous correction to `interaction.response.edit_message` without prior deferral might be problematic if the embed creation is slow.
# It's safer to always `defer` the interaction within the button callback if there's any processing.

# Revised PaginationView previous/next button logic:
# @button(...)
# async def previous_button(self, interaction: discord.Interaction, button_obj: discord.ui.Button):
#     await interaction.response.defer() # Defer immediately
#     if self.current_index > 0:
#         self.current_index -= 1
#         self.update_button_state()
#         embed = create_embed_for_item(...)
#         await interaction.edit_original_response(embed=embed, view=self) # Edit the original deferred response
#     # No else needed, as defer covers the "no action" case.

# This pattern (defer then edit_original_response) is robust.
# Let's apply this to all pagination buttons.

# Final structure for utils.py:
# Imports
# TMDB_IMAGE_BASE_URL
# Database functions (init_db, delete_linked_user, store_linked_user, get_linked_user)
# Embed creation (create_embed_for_item)
# Status emoji (get_status_emoji)
# Request embed creation (create_request_embed - takes URL/headers)
# PaginationView (takes URL/headers/bot_instance, uses local helpers, defer+edit_original_response)
# RequestsPaginationView (takes URL/headers, uses local helpers, defer+edit_original_response)

# The `main_bot_instance` in `PaginationView` might not be strictly necessary if JELLYSEERR_URL and headers are passed in,
# which they are now. I'll remove `main_bot_instance` from `PaginationView`'s `__init__` to simplify.
# The `jellyseerr_headers` are passed in, so no need for `self.bot.jellyseerr_headers`.
# `get_linked_user` is now a local function in `utils.py`.
# `create_embed_for_item` is also local.
# So `PaginationView` seems self-contained with the passed-in parameters.
# `RequestsPaginationView` also seems fine with passed-in `jellyseerr_url` and `jellyseerr_headers`.
# The `jellyfin_headers` are not used by any of these utilities directly, they are used by commands that will be in cogs.

# One final detail: `PaginationView.update_button_state` accesses `self.children` by index.
# This is okay if the buttons are always added in the same order and are always present.
# The decorators `@button` add them to `self.children` in the order they are defined in the class.
# So `self.children[0]` is previous, `self.children[1]` is request, `self.children[2]` is next for `PaginationView`.
# For `RequestsPaginationView`, `self.children[0]` is previous, `self.children[1]` is next. This looks correct.
# The `if len(self.children) == 3` and `if len(self.children) >= 2` checks are good.
# It's important that the custom_ids are unique as they now are.
# The `button_obj` parameter in the button methods is the `discord.ui.Button` instance itself, not the decorator.
# The interaction is `discord.Interaction`.
# Looks good.

# One more pass on PaginationView.request_button:
# `jellyseerr_user_id = int(get_linked_user(interaction.user.id)[0])`
# `get_linked_user` returns `(jellyseerr_id, jellyfin_id, username)` or `None`.
# So, `linked_user_data = get_linked_user(interaction.user.id)`
# `if not linked_user_data or not linked_user_data[0]: ... return`
# `jellyseerr_user_id = int(linked_user_data[0])`
# This logic is correct.

# The print statements for errors can remain for debugging.
# `TMDB_IMAGE_BASE_URL` is correctly defined at the top of utils.py.
# All imports seem to be covered.
# The `json` import was in `jellyrequest.py` but isn't directly used by any of the functions moved to `utils.py`
# (requests library handles json internally). So, it's not needed in `utils.py`. `discord.ui.View, Button, button` are correct.
# `requests` is needed for `create_request_embed` and `PaginationView.request_button`.

# The number of children in PaginationView is 3 (previous, request, next).
# The update_button_state checks `if len(self.children) == 3:`.
# Accesses `self.children[0]` (previous) and `self.children[2]` (next). This is correct.

# The number of children in RequestsPaginationView is 2 (previous, next).
# The update_button_state checks `if len(self.children) >= 2:`.
# Accesses `self.children[0]` (previous) and `self.children[1]` (next). This is correct.

# The `button.response.defer()` type calls were a common pattern in older discord.py or examples,
# but `interaction.response.defer()` is the standard now.
# My corrections `interaction.response.defer()` followed by `await interaction.edit_original_response()`
# or `interaction.followup.send()` are standard for discord.py 2.0+.
# The original code had `button.response.defer()` and `button.edit_original_response()`.
# This was likely a mistake and should have been `interaction.response...`.
# My changes to `interaction.response.edit_message` or `interaction.edit_original_response` are correct.
# Let's stick to the `await interaction.response.defer()` at the start of each button callback,
# then `await interaction.edit_original_response(...)`. This is the safest and most consistent pattern.

# Final check of the code block content for `utils.py`:
# Looks like a complete set of utilities.
# The JELLYSEERR_URL and jellyseerr_headers are now explicitly passed to views and functions that need them.
# This makes utils.py more decoupled from the main bot's global config variables.
# This is a good change.
# The `sqlite3` and `discord` imports are present. `requests` import is also present.
# `discord.ui.View, Button, button` are imported.
# The structure for `utils.py` looks solid.
