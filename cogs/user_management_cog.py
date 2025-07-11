import discord
from discord.ext import commands
from discord import app_commands # Added for slash commands
import requests
import re
import secrets

# Adjust import path for utils
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import store_linked_user, get_linked_user, delete_linked_user

class UserManagementCog(commands.Cog):
    def __init__(self, bot, jellyseerr_url, jellyseerr_headers, jellyfin_url, jellyfin_headers):
        self.bot = bot
        self.jellyseerr_url = jellyseerr_url
        self.jellyseerr_headers = jellyseerr_headers
        self.jellyfin_url = jellyfin_url
        self.jellyfin_headers = jellyfin_headers

    @app_commands.command(name="invite", description="Adds a user to Jellyseerr and Jellyfin.")
    @app_commands.checks.has_permissions(administrator=True) # Corrected decorator
    async def invite_cmd(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        username = re.sub(r"[^a-zA-Z0-9.-]", "", user.name) # Sanitize username
        temp_password = secrets.token_urlsafe(12)

        # Step 1: Create Jellyfin User
        jellyfin_user_id = None
        try:
            jellyfin_user_payload = {
                "Name": username, "Password": temp_password,
                "Policy": { "IsAdministrator": False, "EnableUserPreferenceAccess": True,
                            "EnableMediaPlayback": True, "EnableLiveTvAccess": False,
                            "EnableLiveTvManagement": False }
            }
            jellyfin_new_user_url = f"{self.jellyfin_url}/Users/New"
            response_fin = requests.post(jellyfin_new_user_url, headers=self.jellyfin_headers, json=jellyfin_user_payload, timeout=10)

            if response_fin.status_code == 400 and "User with the same name already exists" in response_fin.text:
                 await interaction.followup.send(f"⚠️ User '{username}' already exists in Jellyfin. Cannot proceed.", ephemeral=True)
                 return
            response_fin.raise_for_status()
            jellyfin_user_id = response_fin.json().get("Id")
            if not jellyfin_user_id:
                await interaction.followup.send("❌ Failed to get user ID from Jellyfin response after creation.", ephemeral=True)
                return
        except requests.exceptions.RequestException as e:
            err_msg = f"❌ Failed to create Jellyfin user: {e}"
            if e.response is not None:
                err_msg += f" - {e.response.text}"
            await interaction.followup.send(err_msg, ephemeral=True)
            return

        # Step 2: Import User to Jellyseerr
        jellyseerr_user = None
        try:
            jellyseerr_import_url = f"{self.jellyseerr_url}/api/v1/user/import-from-jellyfin"
            response_seerr_import = requests.post(
                jellyseerr_import_url, headers=self.jellyseerr_headers,
                json={"jellyfinUserIds": [jellyfin_user_id]}, timeout=10
            )
            response_seerr_import.raise_for_status()
            created_users = response_seerr_import.json()
            if not created_users or not isinstance(created_users, list) or len(created_users) == 0:
                await interaction.followup.send("❌ User created in Jellyfin but import to Jellyseerr returned unexpected data.", ephemeral=True)
                return
            jellyseerr_user = created_users[0]
            if not jellyseerr_user or not jellyseerr_user.get("id"):
                 await interaction.followup.send("❌ User created in Jellyfin but import to Jellyseerr failed to provide a user ID.", ephemeral=True)
                 return
        except requests.exceptions.RequestException as e:
            err_msg = f"❌ Failed to import Jellyfin user to Jellyseerr: {e}"
            if e.response is not None:
                err_msg += f" - {e.response.text}"
            await interaction.followup.send(err_msg, ephemeral=True)
            # Potentially roll back Jellyfin user creation or notify admin
            return

        # Step 3: Store linked user (linking Discord ID to Jellyseerr ID and Jellyfin ID)
        store_linked_user(
            discord_id=str(user.id),
            jellyseerr_user_id=str(jellyseerr_user.get("id")),
            jellyfin_user_id=str(jellyfin_user_id),
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
                f"🔗 Jellyfin: {self.jellyfin_url}\n"
                f"🔗 Jellyseerr: {self.jellyseerr_url}"
            )
            await user.send(dm_message)
        except discord.Forbidden:
            await interaction.followup.send(f"✅ Accounts created for {username}, but I could not DM them. Please send their password manually: `{temp_password}`", ephemeral=True)
            return
        except Exception as e: # Catch other potential errors during DM
            await interaction.followup.send(f"✅ Accounts created for {username}, but failed to DM them. Password: `{temp_password}`. Error: {e}", ephemeral=True)
            return

        await interaction.followup.send(f"✅ Successfully created accounts for `{username}` and sent them a DM with credentials.", ephemeral=True)

    @app_commands.command(name="link", description="Link your Discord account to your Jellyfin/Jellyseerr user")
    async def link_cmd(self, interaction: discord.Interaction, jellyfin_username: str, password: str):
        await interaction.response.defer(ephemeral=True)

        # Step 1: Authenticate with Jellyfin
        jellyfin_user_id = None
        try:
            auth_payload = {"Username": jellyfin_username, "Pw": password}
            jellyfin_auth_url = f"{self.jellyfin_url}/Users/AuthenticateByName"
            # Note: Jellyfin's AuthenticateByName might not require X-Emby-Token if it's for initial auth.
            # However, if the server is locked down, it might. The original code included it.
            auth_response = requests.post(jellyfin_auth_url, json=auth_payload, headers=self.jellyfin_headers, timeout=10)

            if auth_response.status_code == 401:
                await interaction.followup.send("❌ **Authentication Failed:** Invalid Jellyfin username or password.", ephemeral=True)
                return
            auth_response.raise_for_status()
            jellyfin_user_data = auth_response.json()
            jellyfin_user_id = jellyfin_user_data.get("User", {}).get("Id")
            if not jellyfin_user_id:
                await interaction.followup.send("❌ **Error:** Could not retrieve Jellyfin User ID after authentication.", ephemeral=True)
                return
        except requests.exceptions.RequestException as e:
            await interaction.followup.send(f"❌ An error occurred while trying to authenticate with Jellyfin: {e}", ephemeral=True)
            return

        # Step 2: Find the corresponding Jellyseerr user by Jellyfin User ID
        jellyseerr_user_id_for_link = None
        jellyseerr_username = None # To store the username from Jellyseerr if found
        try:
            seerr_users_url = f"{self.jellyseerr_url}/api/v1/user?take=1000" # Get many users
            seerr_response = requests.get(seerr_users_url, headers=self.jellyseerr_headers, timeout=10)
            seerr_response.raise_for_status()
            seerr_users = seerr_response.json().get("results", [])

            found_seerr_user = next((u for u in seerr_users if str(u.get("jellyfinUserId")) == str(jellyfin_user_id)), None)

            if not found_seerr_user:
                await interaction.followup.send(
                    f"⚠️ **Account Not Found in Jellyseerr.** Although your Jellyfin login is correct, "
                    f"your account ('{jellyfin_username}') has not been imported or linked in Jellyseerr. Please contact an administrator.",
                    ephemeral=True
                )
                return
            jellyseerr_user_id_for_link = found_seerr_user.get("id")
            jellyseerr_username = found_seerr_user.get("username") or found_seerr_user.get("jellyfinUsername") or jellyfin_username

        except requests.exceptions.RequestException as e:
            await interaction.followup.send(f"❌ Failed to fetch users from Jellyseerr: {e}", ephemeral=True)
            return

        if not jellyseerr_user_id_for_link:
             await interaction.followup.send(f"❌ Could not determine Jellyseerr user ID for linking. Please contact an administrator.", ephemeral=True)
             return

        # Step 3: Store the linked user in the database
        store_linked_user(
            discord_id=str(interaction.user.id), # Corrected: use interaction.user.id
            jellyseerr_user_id=str(jellyseerr_user_id_for_link),
            jellyfin_user_id=str(jellyfin_user_id), # Storing this too for completeness
            username=jellyseerr_username # Store the Jellyseerr username
        )
        await interaction.followup.send(f"✅ **Success!** Your Discord account is now linked to the Jellyfin/Jellyseerr user '{jellyseerr_username}'.", ephemeral=True)

    @app_commands.command(name="unlink", description="Unlink your Discord account from Jellyseerr/Jellyfin")
    async def unlink_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        linked_user = get_linked_user(str(interaction.user.id)) # Corrected: use interaction.user.id
        if not linked_user:
            await interaction.followup.send("⚠️ You haven't linked your account yet.", ephemeral=True)
            return

        delete_linked_user(str(interaction.user.id)) # Corrected: use interaction.user.id
        await interaction.followup.send("✅ Unlinked your Discord account successfully.", ephemeral=True)


async def setup(bot):
    jellyseerr_url = getattr(bot, 'JELLYSEERR_URL', None)
    jellyseerr_api_key = getattr(bot, 'JELLYSEERR_API_KEY', None)
    jellyfin_url = getattr(bot, 'JELLYFIN_URL', None)
    jellyfin_api_key = getattr(bot, 'JELLYFIN_API_KEY', None)

    if not all([jellyseerr_url, jellyseerr_api_key, jellyfin_url, jellyfin_api_key]):
        raise ValueError("JELLYSEERR_URL, JELLYSEERR_API_KEY, JELLYFIN_URL, and JELLYFIN_API_KEY must be set on the bot instance to load UserManagementCog.")

    jellyseerr_headers = {"X-Api-Key": jellyseerr_api_key, "Content-Type": "application/json"}
    jellyfin_headers = {"X-Emby-Token": jellyfin_api_key, "Content-Type": "application/json"}

    await bot.add_cog(UserManagementCog(bot, jellyseerr_url, jellyseerr_headers, jellyfin_url, jellyfin_headers))
