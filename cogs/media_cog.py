import discord
from discord.ext import commands
from discord import app_commands # Added for slash commands
from urllib.parse import urlencode, quote
import requests

# Assuming utils.py is in the parent directory relative to cogs directory
# For robust imports, especially if running the bot from the root directory:
# from utils import create_embed_for_item, PaginationView
# If running from a different working directory, sys.path manipulation or package structure might be needed.
# For now, using a relative import path that should work if the bot is started from the root.
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import create_embed_for_item, PaginationView, get_linked_user # Added get_linked_user

class MediaCommandsCog(commands.Cog):
    def __init__(self, bot, jellyseerr_url, jellyseerr_headers):
        self.bot = bot
        self.jellyseerr_url = jellyseerr_url
        self.jellyseerr_headers = jellyseerr_headers

    @app_commands.command(name="request", description="Search for a movie or TV show")
    async def request_cmd(self, interaction: discord.Interaction, query: str):
        """Searches for media on Jellyseerr and displays results with pagination."""
        await interaction.response.defer()

        search_url_path = "/api/v1/search"
        full_search_url = f"{self.jellyseerr_url}{search_url_path}"
        params = urlencode({"query": query}, quote_via=quote)

        try:
            response = requests.get(f"{full_search_url}?{params}", headers=self.jellyseerr_headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])

            # print(f"Search results for '{query}': {results}") # Debugging line

            if not results:
                await interaction.followup.send("No results found for your query.")
                return

            # Pass JELLYSEERR_URL and headers to the PaginationView
            view = PaginationView(results, self.jellyseerr_url, self.jellyseerr_headers)
            initial_embed = create_embed_for_item(results[0], 0, len(results))

            await interaction.followup.send(embed=initial_embed, view=view)

        except requests.exceptions.RequestException as e:
            await interaction.followup.send(f"An error occurred while searching: {e}")
        except Exception as e: # Catch any other unexpected errors
            await interaction.followup.send(f"An unexpected error occurred: {e}")


    @app_commands.command(name="discover", description="Discover new movies or TV shows")
    async def discover_cmd(self, interaction: discord.Interaction):
        """Discovers new movies or TV shows from Jellyseerr."""
        await interaction.response.defer()
        try:
            # Define API paths
            movies_discover_path = "/api/v1/discover/movies"
            tv_discover_path = "/api/v1/discover/tv"

            # Make requests
            movie_response = requests.get(f"{self.jellyseerr_url}{movies_discover_path}", headers=self.jellyseerr_headers, timeout=10)
            tv_response = requests.get(f"{self.jellyseerr_url}{tv_discover_path}", headers=self.jellyseerr_headers, timeout=10)

            movie_response.raise_for_status()
            tv_response.raise_for_status()

            movies = movie_response.json().get("results", [])
            tv_shows = tv_response.json().get("results", [])

            popular_items = movies + tv_shows
            if not popular_items:
                await interaction.followup.send("No popular items found to discover.")
                return

            # Shuffle popular_items to provide variety if desired, or sort them
            # For now, using as is.

            # Pass JELLYSEERR_URL and headers to the PaginationView
            view = PaginationView(popular_items, self.jellyseerr_url, self.jellyseerr_headers)
            initial_embed = create_embed_for_item(popular_items[0], 0, len(popular_items))
            await interaction.followup.send(embed=initial_embed, view=view)

        except requests.exceptions.RequestException as e:
            await interaction.followup.send(f"An error occurred while fetching popular items: {e}")
        except Exception as e: # Catch any other unexpected errors
            await interaction.followup.send(f"An unexpected error occurred during discovery: {e}")

async def setup(bot):
    # This function is called by discord.py when loading the cog
    # We need to pass the JELLYSEERR_URL and JELLYSEERR_API_KEY (or headers) from the bot's config
    # This assumes the main bot instance will have these attributes or a config dictionary
    jellyseerr_url = getattr(bot, 'JELLYSEERR_URL', None)
    jellyseerr_api_key = getattr(bot, 'JELLYSEERR_API_KEY', None)

    if not jellyseerr_url or not jellyseerr_api_key:
        raise ValueError("JELLYSEERR_URL and JELLYSEERR_API_KEY must be set on the bot instance to load MediaCommandsCog.")

    jellyseerr_headers = {
        "X-Api-Key": jellyseerr_api_key,
        "Content-Type": "application/json"
    }
    await bot.add_cog(MediaCommandsCog(bot, jellyseerr_url, jellyseerr_headers))
