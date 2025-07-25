import discord
from discord.ext import commands
import os # For listing files in cogs directory
import asyncio # For setup_hook if needed, though direct loading is also fine

# Import utilities, especially init_db
import utils

# --- Configuration ---
# These should ideally be loaded from environment variables or a config file for security
JELLYSEERR_URL = os.getenv("JELLYSEERR_URL", "https://requests.example.com")
JELLYSEERR_API_KEY = os.getenv("JELLYSEERR_API_KEY", "YOUR_JELLYSEERR_API_KEY") # Example, replace
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "YOUR_DISCORD_BOT_TOKEN") # Replace with your actual token
JELLYFIN_URL = os.getenv("JELLYFIN_URL", "https://tv.example.com")
JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY", "YOUR_JELLYFIN_API_KEY") # Example, replace
# ---------------------

# Define a custom Bot class to handle setup_hook for loading cogs
class JellyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store config directly on the bot instance so cogs can access it.
        self.JELLYSEERR_URL = JELLYSEERR_URL
        self.JELLYSEERR_API_KEY = JELLYSEERR_API_KEY
        self.JELLYFIN_URL = JELLYFIN_URL
        self.JELLYFIN_API_KEY = JELLYFIN_API_KEY

    async def setup_hook(self):
        print("Running setup_hook...")
        # Manually load all cogs
        import importlib 
        cogs_path = "cogs"
        
        cog_files = [f[:-3] for f in os.listdir(cogs_path) if f.endswith(".py") and not f.startswith("__")]

        for cog_module_name in cog_files:
            full_module_path = f"{cogs_path}.{cog_module_name}"
            try:
                print(f"Attempting to manually load module: {full_module_path}")
                module = importlib.import_module(full_module_path)
                print(f"Successfully imported module: {full_module_path}")
                
                if hasattr(module, 'setup'):
                    await module.setup(self)
                    print(f"Successfully setup and loaded cog: {full_module_path}")
                else:
                    print(f"No setup function found in {full_module_path}")
            except Exception as e:
                print(f"Failed to manually load cog {full_module_path}: {e}")
                # Consider re-raising or handling more gracefully depending on severity.
        
        # Sync application commands globally
        print("Attempting to sync application commands...")
        try:
            await self.tree.sync() # Sync globally
            print("Application commands synced successfully.")
        except Exception as e:
            print(f"Error syncing application commands: {e}")
        
# --- Bot Instantiation ---
intents = discord.Intents.default()
# If using traditional prefix commands (not slash), message content intent might be needed.
# intents.message_content = True
bot = JellyBot(command_prefix="/", intents=intents)

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
        print("Bot is running with username:", bot.user.name)