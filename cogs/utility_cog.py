import discord
from discord.ext import commands
import requests

# Adjust import path for utils
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import get_linked_user, create_request_embed, RequestsPaginationView

class UtilityCog(commands.Cog):
    def __init__(self, bot, jellyfin_url, jellyfin_headers, jellyseerr_url, jellyseerr_headers):
        self.bot = bot
        self.jellyfin_url = jellyfin_url
        self.jellyfin_headers = jellyfin_headers
        self.jellyseerr_url = jellyseerr_url
        self.jellyseerr_headers = jellyseerr_headers

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Logged in as {self.bot.user.name} (from UtilityCog)")
        print("Bot is ready to receive commands (from UtilityCog).")

    @commands.slash_command(name="watch", description="Get your watch statistics from Jellyfin")
    async def watch_stats_cmd(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True) # Ephemeral for privacy

        linked_user = get_linked_user(str(ctx.author.id))
        if not linked_user:
            await ctx.followup.send("⚠️ You haven't linked your account yet. Use `/link` to get started.", ephemeral=True)
            return

        _, jellyfin_user_id, username = linked_user # Unpack: jellyseerr_id, jellyfin_id, username
        if not jellyfin_user_id:
            await ctx.followup.send("⚠️ Your Jellyfin User ID is not found in the link. Please try linking again or contact an admin.", ephemeral=True)
            return

        # Query Jellyfin watch data
        items_url = f"{self.jellyfin_url}/Users/{jellyfin_user_id}/Items"
        params = {
            "Recursive": "true", "IncludeItemTypes": "Movie,Episode",
            "Filters": "IsPlayed", "Fields": "RunTimeTicks,UserData,SeriesName"
        }

        try:
            response = requests.get(items_url, headers=self.jellyfin_headers, params=params, timeout=15)
            response.raise_for_status()
            items = response.json().get("Items", [])
        except requests.exceptions.RequestException as e:
            await ctx.followup.send(f"❌ Failed to fetch watch data from Jellyfin: {e}", ephemeral=True)
            return
        except Exception as e: # Catch any other unexpected errors
            await ctx.followup.send(f"❌ An unexpected error occurred while fetching watch data: {e}", ephemeral=True)
            return


        watched_count = len(items)
        total_ticks = sum(item.get("RunTimeTicks", 0) for item in items if item.get("RunTimeTicks")) # Ensure ticks exist
        total_seconds = total_ticks / 10_000_000 # Ticks are 100 nanoseconds

        days, remainder_seconds = divmod(total_seconds, 86400) # 24*60*60
        hours, remainder_seconds = divmod(remainder_seconds, 3600) # 60*60
        minutes, _ = divmod(remainder_seconds, 60)

        # Find last watched item (more robustly)
        last_watched_item = None
        if items:
            # Filter items that have UserData and LastPlayedDate
            valid_items_for_last_played = [
                item for item in items
                if item.get("UserData") and item.get("UserData").get("LastPlayedDate")
            ]
            if valid_items_for_last_played:
                last_watched_item = max(
                    valid_items_for_last_played,
                    key=lambda x: x["UserData"]["LastPlayedDate"]
                )

        embed = discord.Embed(
            title=f"📊 {ctx.author.display_name}'s Watch Statistics",
            color=discord.Color.blue()
        )
        embed.add_field(name="📺 Total Watched Items", value=str(watched_count), inline=False)
        embed.add_field(name="⏱️ Total Watch Time", value=f"{int(days)}d {int(hours)}h {int(minutes)}m", inline=False)

        if last_watched_item:
            title = last_watched_item.get("Name", "Unknown Title")
            if last_watched_item.get("Type") == "Episode" and last_watched_item.get("SeriesName"):
                title = f"{last_watched_item.get('SeriesName')} - {title}"
            embed.add_field(name="👀 Last Watched", value=title, inline=False)
        else:
            embed.add_field(name="👀 Last Watched", value="No specific last watched item found.", inline=False)

        await ctx.followup.send(embed=embed, ephemeral=True)

    @commands.slash_command(name="requests", description="View the status of your media requests")
    async def my_requests_cmd(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)

        linked_user = get_linked_user(str(ctx.author.id))
        if not linked_user or not linked_user[0]: # Check for linked user and jellyseerr_id
            await ctx.followup.send("⚠️ You need to link your account first using `/link`.", ephemeral=True)
            return

        jellyseerr_user_id = linked_user[0]

        try:
            request_api_url = f"{self.jellyseerr_url}/api/v1/request"
            params = { "take": 100, "skip": 0, "sort": "added",
                       "filter": "all", "requestedBy": jellyseerr_user_id }

            response = requests.get(request_api_url, headers=self.jellyseerr_headers, params=params, timeout=10)
            response.raise_for_status()
            user_requests_data = response.json().get("results", [])

        except requests.exceptions.RequestException as e:
            await ctx.followup.send(f"❌ An error occurred while fetching your requests: {e}", ephemeral=True)
            return
        except Exception as e: # Catch any other unexpected errors
            await ctx.followup.send(f"❌ An unexpected error occurred: {e}", ephemeral=True)
            return

        if not user_requests_data:
            await ctx.followup.send("You have no pending or completed requests.", ephemeral=True)
            return

        user_requests_data.sort(key=lambda r: r.get('createdAt', ''), reverse=True)

        # Pass JELLYSEERR_URL and headers to the RequestsPaginationView
        view = RequestsPaginationView(user_requests_data, self.jellyseerr_url, self.jellyseerr_headers)
        initial_embed = create_request_embed(
            user_requests_data[0], 0, len(user_requests_data),
            self.jellyseerr_url, self.jellyseerr_headers # Pass URL and headers
        )

        await ctx.followup.send(embed=initial_embed, view=view, ephemeral=True)

def setup(bot):
    jellyfin_url = getattr(bot, 'JELLYFIN_URL', None)
    jellyfin_api_key = getattr(bot, 'JELLYFIN_API_KEY', None)
    jellyseerr_url = getattr(bot, 'JELLYSEERR_URL', None)
    jellyseerr_api_key = getattr(bot, 'JELLYSEERR_API_KEY', None)

    if not all([jellyfin_url, jellyfin_api_key, jellyseerr_url, jellyseerr_api_key]):
        raise ValueError("JELLYFIN_URL, JELLYFIN_API_KEY, JELLYSEERR_URL, and JELLYSEERR_API_KEY must be set on the bot instance to load UtilityCog.")

    jellyfin_headers = {"X-Emby-Token": jellyfin_api_key, "Content-Type": "application/json"}
    jellyseerr_headers = {"X-Api-Key": jellyseerr_api_key, "Content-Type": "application/json"}

    bot.add_cog(UtilityCog(bot, jellyfin_url, jellyfin_headers, jellyseerr_url, jellyseerr_headers))
