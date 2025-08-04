import discord
from discord.ext import commands, tasks
from discord import app_commands
import requests
import re
import secrets
from datetime import datetime, timedelta

# Ensure utils.py can be imported from the parent directory.
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils import store_linked_user, get_linked_user, delete_linked_user, get_all_expiring_users

class UserManagementCog(commands.Cog):
    def __init__(self, bot, jellyseerr_url, jellyseerr_headers, jellyfin_url, jellyfin_headers):
        self.bot = bot
        self.jellyseerr_url = jellyseerr_url
        self.jellyseerr_headers = jellyseerr_headers
        self.jellyfin_url = jellyfin_url
        self.jellyfin_headers = jellyfin_headers
        self.check_expired_users.start()

    def cog_unload(self):
        self.check_expired_users.cancel()

    @tasks.loop(hours=24)
    async def check_expired_users(self):
        now = datetime.utcnow()
        expiring_users = get_all_expiring_users()
        for user_row in expiring_users:
            # Unpack with None defaults for backward compatibility
            discord_id, jellyfin_user_id, expires_at_str, guild_id, role_name = (*user_row, None, None)[:5]

            if not expires_at_str:
                continue
            expires_at = datetime.fromisoformat(expires_at_str)

            if now >= expires_at:
                try:
                    # --- Role Removal ---
                    if guild_id and role_name:
                        try:
                            guild = self.bot.get_guild(int(guild_id))
                            if guild:
                                role = discord.utils.get(guild.roles, name=role_name)
                                if role:
                                    member = await guild.fetch_member(int(discord_id))
                                    if member:
                                        await member.remove_roles(role)
                                        print(f"Removed role '{role_name}' from user {discord_id}.")
                                else:
                                    print(f"Role '{role_name}' not found in guild {guild_id} for user {discord_id}.")
                            else:
                                print(f"Guild {guild_id} not found for user {discord_id}.")
                        except discord.Forbidden:
                            print(f"Bot lacks permissions to remove role '{role_name}' for user {discord_id} in guild {guild_id}.")
                        except discord.NotFound:
                             print(f"Member {discord_id} not found in guild {guild_id} for role removal.")
                        except Exception as e:
                            print(f"An error occurred during role removal for {discord_id}: {e}")


                    # --- Disable in Jellyfin ---
                    policy_url = f"{self.jellyfin_url}/Users/{jellyfin_user_id}/Policy"
                    response = requests.get(policy_url, headers=self.jellyfin_headers, timeout=10)
                    response.raise_for_status()
                    policy = response.json()
                    policy['EnableMediaPlayback'] = False
                    requests.post(policy_url, headers=self.jellyfin_headers, json=policy, timeout=10).raise_for_status()
                    print(f"Disabled Jellyfin access for expired user: {discord_id}")

                    # --- Notify user and cleanup DB ---
                    try:
                        user = await self.bot.fetch_user(int(discord_id))
                        await user.send("Your temporary access to the media server has expired, and any associated roles have been removed.")
                    except discord.NotFound:
                        print(f"Could not find Discord user {discord_id} to notify of expiration.")
                    except discord.Forbidden:
                        print(f"Could not DM user {discord_id} about expiration.")

                    delete_linked_user(discord_id)
                    print(f"Unlinked expired user: {discord_id}")

                except requests.exceptions.RequestException as e:
                    print(f"Failed to disable expired user {discord_id} in Jellyfin: {e}")
                except Exception as e:
                    print(f"An unexpected error occurred while processing expiration for user {discord_id}: {e}")

    @check_expired_users.before_loop
    async def before_check_expired_users(self):
        await self.bot.wait_until_ready()

    async def _create_user(self, interaction: discord.Interaction, user: discord.Member, duration_days: int = None, role_name_to_assign: str = None):
        """A helper function to create a user in Jellyfin and Jellyseerr, with an optional expiration."""
        await interaction.response.defer(ephemeral=True)
        username = re.sub(r"[^a-zA-Z0-9.-]", "", user.name)
        temp_password = secrets.token_urlsafe(12)

        # Create Jellyfin User
        try:
            jellyfin_user_payload = {
                "Name": username, "Password": temp_password,
                "Policy": { "IsAdministrator": False, "EnableUserPreferenceAccess": True,
                            "EnableMediaPlayback": True, "EnableLiveTvAccess": False,
                            "EnableLiveTvManagement": False }
            }
            response_fin = requests.post(f"{self.jellyfin_url}/Users/New", headers=self.jellyfin_headers, json=jellyfin_user_payload, timeout=10)
            if response_fin.status_code == 400 and "User with the same name already exists" in response_fin.text:
                await interaction.followup.send(f"⚠️ User '{username}' already exists in Jellyfin.", ephemeral=True)
                return
            response_fin.raise_for_status()
            jellyfin_user_id = response_fin.json().get("Id")
        except requests.exceptions.RequestException as e:
            await interaction.followup.send(f"❌ Failed to create Jellyfin user: {e}", ephemeral=True)
            return

        # Import User to Jellyseerr
        try:
            response_seerr_import = requests.post(f"{self.jellyseerr_url}/api/v1/user/import-from-jellyfin",
                                                 headers=self.jellyseerr_headers, json={"jellyfinUserIds": [jellyfin_user_id]}, timeout=10)
            response_seerr_import.raise_for_status()
            jellyseerr_user = response_seerr_import.json()[0]
        except requests.exceptions.RequestException as e:
            await interaction.followup.send(f"❌ Failed to import to Jellyseerr: {e}", ephemeral=True)
            return

        # Assign role if specified
        if role_name_to_assign:
            role = discord.utils.get(interaction.guild.roles, name=role_name_to_assign)
            if role:
                try:
                    await user.add_roles(role)
                except discord.Forbidden:
                    # Can't add role, but continue with user creation. Notify in the final message.
                    print(f"Failed to assign role '{role_name_to_assign}' to {user.name}: Bot is missing permissions.")
                except Exception as e:
                    print(f"An unexpected error occurred while assigning role '{role_name_to_assign}' to {user.name}: {e}")
            else:
                print(f"Role '{role_name_to_assign}' not found in guild '{interaction.guild.name}'.")


        # Store linked user
        expires_at = datetime.utcnow() + timedelta(days=duration_days) if duration_days else None
        store_linked_user(
            discord_id=str(user.id),
            jellyseerr_user_id=str(jellyseerr_user.get("id")),
            jellyfin_user_id=str(jellyfin_user_id),
            username=username,
            expires_at=expires_at.isoformat() if expires_at else None,
            guild_id=str(interaction.guild.id) if role_name_to_assign else None,
            role_name=role_name_to_assign
        )

        # DM Credentials
        try:
            dm_message = (
                f"## Welcome to the Media Server! 🎉\n\n"
                f"An account has been created for you. Here are your login details:\n\n"
                f"**Username:** `{username}`\n"
                f"**Temporary Password:** `{temp_password}`\n\n"
                f"Please change your password after logging in.\n\n"
                f"🔗 Jellyfin: {self.jellyfin_url}\n"
                f"🔗 Jellyseerr: {self.jellyseerr_url}\n\n"
            )
            if duration_days:
                dm_message += f"**Note:** This is a temporary account that will expire in {duration_days} days."

            await user.send(dm_message)
            await interaction.followup.send(f"✅ Successfully created account for `{username}` and sent them a DM.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(f"✅ Account for {username} created, but I could not DM them. Password: `{temp_password}`", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"✅ Account for {username} created, but failed to DM. Password: `{temp_password}`. Error: {e}", ephemeral=True)

    @app_commands.command(name="invite", description="Adds a permanent user to Jellyseerr and Jellyfin.")
    @app_commands.checks.has_permissions(administrator=True)
    async def invite_cmd(self, interaction: discord.Interaction, user: discord.Member):
        await self._create_user(interaction, user, duration_days=None)

    @app_commands.command(name="trial", description="Adds a trial user for 7 days.")
    @app_commands.checks.has_permissions(administrator=True)
    async def trial_cmd(self, interaction: discord.Interaction, user: discord.Member):
        await self._create_user(interaction, user, duration_days=7, role_name_to_assign="Trial")

    @app_commands.command(name="vip", description="Adds a VIP user for 30 days.")
    @app_commands.checks.has_permissions(administrator=True)
    async def vip_cmd(self, interaction: discord.Interaction, user: discord.Member):
        await self._create_user(interaction, user, duration_days=30, role_name_to_assign="VIP")

    @app_commands.command(name="link", description="Link your Discord account to your Jellyfin/Jellyseerr user")
    async def link_cmd(self, interaction: discord.Interaction, jellyfin_username: str, password: str):
        await interaction.response.defer(ephemeral=True)

        # Authenticate with Jellyfin
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

        # Find the corresponding Jellyseerr user by Jellyfin User ID
        jellyseerr_user_id_for_link = None
        jellyseerr_username = None # To store the username from Jellyseerr if found
        try:
            seerr_users_url = f"{self.jellyseerr_url}/api/v1/user?take=1000" # Get many users, default is 20
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

        # Store the linked user in the database
        store_linked_user(
            discord_id=str(interaction.user.id),
            jellyseerr_user_id=str(jellyseerr_user_id_for_link),
            jellyfin_user_id=str(jellyfin_user_id), # Storing this for completeness
            username=jellyseerr_username
        )
        await interaction.followup.send(f"✅ **Success!** Your Discord account is now linked to the Jellyfin/Jellyseerr user '{jellyseerr_username}'.", ephemeral=True)

    @app_commands.command(name="unlink", description="Unlink your Discord account from Jellyseerr/Jellyfin")
    async def unlink_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        linked_user = get_linked_user(str(interaction.user.id))
        if not linked_user:
            await interaction.followup.send("⚠️ You haven't linked your account yet.", ephemeral=True)
            return

        delete_linked_user(str(interaction.user.id))
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
