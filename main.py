import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime
import asyncio

# --- ENV VAR VALIDATION ---
def get_env_var(name, required=True, is_int=False):
    value = os.getenv(name)
    if value is None:
        if required:
            print(f"[ERROR] Environment variable '{name}' is missing.")
        return None
    try:
        return int(value) if is_int else value
    except ValueError:
        print(f"[ERROR] Environment variable '{name}' should be an integer, but got: {value}")
        return None

DISCORD_BOT_TOKEN = get_env_var("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = get_env_var("PANEL_CHANNEL_ID", is_int=True)
LOG_CHANNEL_ID = get_env_var("LOG_CHANNEL_ID", is_int=True)
LEADERBOARD_CHANNEL_ID = get_env_var("LEADERBOARD_CHANNEL_ID", is_int=True)
BACKUP_CHANNEL_ID = get_env_var("BACKUP_CHANNEL_ID", is_int=True)

if not all([DISCORD_BOT_TOKEN, PANEL_CHANNEL_ID, LOG_CHANNEL_ID, LEADERBOARD_CHANNEL_ID, BACKUP_CHANNEL_ID]):
    raise ValueError("One or more environment variables are not set correctly.")

# --- DISCORD SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

class WorkPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.log_action(interaction.user, "Clocked In")
        await interaction.response.send_message("You clocked in!", ephemeral=True)

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.log_action(interaction.user, "Clocked Out")
        await interaction.response.send_message("You clocked out!", ephemeral=True)

    @discord.ui.button(label="Upgrade Car", style=discord.ButtonStyle.primary, custom_id="upgrade_car")
    async def upgrade_car(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.log_action(interaction.user, "Upgraded Car")
        await interaction.response.send_message("Car upgraded!", ephemeral=True)

    @discord.ui.button(label="Upgrade Bike", style=discord.ButtonStyle.primary, custom_id="upgrade_bike")
    async def upgrade_bike(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.log_action(interaction.user, "Upgraded Bike")
        await interaction.response.send_message("Bike upgraded!", ephemeral=True)

    @discord.ui.button(label="Install Part", style=discord.ButtonStyle.secondary, custom_id="install_part")
    async def install_part(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.log_action(interaction.user, "Installed a Part")
        await interaction.response.send_message("Part installed!", ephemeral=True)

    async def log_action(self, user, action):
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"{user.mention} {action} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.add_view(WorkPanel())

    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        # Delete old bot messages to keep panel clean
        async for msg in panel_channel.history(limit=50):
            if msg.author == bot.user:
                await msg.delete()

        await panel_channel.send("**Work Panel**", view=WorkPanel())

bot.run(DISCORD_BOT_TOKEN)
