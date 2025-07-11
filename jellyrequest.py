import discord
from discord.ext import commands
import os # For listing files in cogs directory
import asyncio # For setup_hook if needed, though direct loading is also fine

# Import utilities, especially init_db
import utils

# --- Configuration ---
# These should ideally be loaded from environment variables or a config file for security
JELLYSEERR_URL = os.getenv("JELLYSEERR_URL", "https://requests.demonbox.co")
JELLYSEERR_API_KEY = os.getenv("JELLYSEERR_API_KEY", "MTc1MTI3MTE1NzE3OTNhZjRmYjMxLTEzYWUtNGMyNi04ZDMwLWIzNzNiMTI3MGY2OA==") # Example, replace
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "YOUR_DISCORD_BOT_TOKEN") # Replace with your actual token
JELLYFIN_URL = os.getenv("JELLYFIN_URL", "https://tv.demonbox.co")
JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY", "YOUR_JELLYFIN_API_KEY") # Example, replace
# TMDB_IMAGE_BASE_URL is now in utils.py as it's used there

# ---------------------

# Define a custom Bot class to handle setup_hook for loading cogs
class JellyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store config directly on the bot instance so cogs can access it via self.bot.JELLYSEERR_URL etc.
        self.JELLYSEERR_URL = JELLYSEERR_URL
        self.JELLYSEERR_API_KEY = JELLYSEERR_API_KEY
        self.JELLYFIN_URL = JELLYFIN_URL
        self.JELLYFIN_API_KEY = JELLYFIN_API_KEY
        # Headers can also be constructed here and stored if preferred, or cogs can make them.
        # For simplicity with current cog setup, cogs reconstruct headers.

    async def setup_hook(self):
        print("Running setup_hook...")
        # Load cogs
        cogs_path = "cogs"
        for filename in os.listdir(cogs_path):
            if filename.endswith(".py") and not filename.startswith("__"):
                cog_name = f"{cogs_path}.{filename[:-3]}"
                try:
                    await self.load_extension(cog_name)
                    print(f"Successfully loaded cog: {cog_name}")
                except Exception as e:
                    print(f"Failed to load cog {cog_name}: {e}")
                    # Optionally, re-raise or handle more gracefully depending on severity
                    # raise

        # Optional: Sync application commands globally or for specific guilds
        # await self.tree.sync() # Sync globally
        # print("Application commands synced.")


# --- Bot Instantiation ---
intents = discord.Intents.default()
# You might need to enable message content intent if you plan to use prefix commands for non-slash interactions
# intents.message_content = True
bot = JellyBot(command_prefix="/", intents=intents) # Using the custom JellyBot class

# --- Main Execution ---
if __name__ == "__main__":
    # Initialize the database
    utils.init_db()
    print("Database initialized.")

    if DISCORD_BOT_TOKEN == "YOUR_DISCORD_BOT_TOKEN" or not DISCORD_BOT_TOKEN:
        print("ERROR: DISCORD_BOT_TOKEN is not set. Please set it in the script or as an environment variable.")
    else:
        print(f"Attempting to run bot with JELLYSEERR_URL: {JELLYSEERR_URL}, JELLYFIN_URL: {JELLYFIN_URL}")
        bot.run(DISCORD_BOT_TOKEN)