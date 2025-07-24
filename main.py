import os
import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
TOKEN = os.getenv("DISCORD_TOKEN")

# CHANNEL & ROLE IDs
PANEL_CHANNEL_ID = 1344409201123786758
LOG_CHANNEL_ID = 1390028891791298731
LEADERBOARD_CHANNEL_ID = 1364065995408281651
ADMIN_ROLE_ID = 1391785348262264925

# Prices
PRICE_CAR_PART = 50000
PRICE_BIKE_PART = 50000
PRICE_CAR_UPGRADE = 850000
PRICE_BIKE_UPGRADE = 300000
PRICE_ENGINE_UPGRADE = 500000

# In-memory data
work_data = {}

# Logging function
async def log_action(message: str):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"📋 {message}")

# Format time
def format_duration(seconds):
    return str(timedelta(seconds=int(seconds)))

# View class for panel
class WorkPanel(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: ui.Button):
        user_id = str(interaction.user.id)
        user_data = work_data.setdefault(user_id, {"clocked_in": False, "last_clock_in": None, "total_time": 0, "car_parts": 0, "bike_parts": 0, "car_upgrades": 0, "bike_upgrades": 0, "engine_upgrades": 0})
        if user_data["clocked_in"]:
            await interaction.response.send_message("❌ You are already clocked in.", ephemeral=True)
            return
        user_data["clocked_in"] = True
        user_data["last_clock_in"] = datetime.utcnow()
        await interaction.response.send_message("✅ You clocked in.", ephemeral=True)
        await log_action(f"{interaction.user.mention} clocked in at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

    @ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: ui.Button):
        user_id = str(interaction.user.id)
        user_data = work_data.get(user_id)
        if not user_data or not user_data["clocked_in"]:
            await interaction.response.send_message("❌ You are not clocked in.", ephemeral=True)
            return
        session_time = (datetime.utcnow() - user_data["last_clock_in"]).total_seconds()
        user_data["total_time"] += session_time
        user_data["clocked_in"] = False
        user_data["last_clock_in"] = None
        await interaction.response.send_message(f"✅ Clocked out. Time added: {format_duration(session_time)}", ephemeral=True)
        await log_action(f"{interaction.user.mention} clocked out and added {format_duration(session_time)}")

    @ui.button(label="Car Part", style=discord.ButtonStyle.primary, custom_id="car_part")
    async def car_part(self, interaction: discord.Interaction, button: ui.Button):
        await self.register_action(interaction, "car_parts", PRICE_CAR_PART)

    @ui.button(label="Bike Part", style=discord.ButtonStyle.primary, custom_id="bike_part")
    async def bike_part(self, interaction: discord.Interaction, button: ui.Button):
        await self.register_action(interaction, "bike_parts", PRICE_BIKE_PART)

    @ui.button(label="Full Car Upgrade", style=discord.ButtonStyle.success, custom_id="car_upgrade")
    async def car_upgrade(self, interaction: discord.Interaction, button: ui.Button):
        await self.register_action(interaction, "car_upgrades", PRICE_CAR_UPGRADE)

    @ui.button(label="Full Bike Upgrade", style=discord.ButtonStyle.success, custom_id="bike_upgrade")
    async def bike_upgrade(self, interaction: discord.Interaction, button: ui.Button):
        await self.register_action(interaction, "bike_upgrades", PRICE_BIKE_UPGRADE)

    @ui.button(label="Engine Upgrade", style=discord.ButtonStyle.secondary, custom_id="engine_upgrade")
    async def engine_upgrade(self, interaction: discord.Interaction, button: ui.Button):
        await self.register_action(interaction, "engine_upgrades", PRICE_ENGINE_UPGRADE)

    @ui.button(label="Reset Leaderboard", style=discord.ButtonStyle.danger, custom_id="reset_leaderboard")
    async def reset_leaderboard(self, interaction: discord.Interaction, button: ui.Button):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ You don't have permission to reset.", ephemeral=True)
            return
        work_data.clear()
        await interaction.response.send_message("✅ Leaderboard has been reset.", ephemeral=True)
        await log_action(f"🔁 Leaderboard was reset by {interaction.user.mention}")
        await update_leaderboard()

    async def register_action(self, interaction, key, price):
        user_id = str(interaction.user.id)
        user_data = work_data.setdefault(user_id, {"clocked_in": False, "last_clock_in": None, "total_time": 0, "car_parts": 0, "bike_parts": 0, "car_upgrades": 0, "bike_upgrades": 0, "engine_upgrades": 0})
        if not user_data["clocked_in"]:
            await interaction.response.send_message("❌ You must clock in first.", ephemeral=True)
            return
        user_data[key] += 1
        await interaction.response.send_message(f"✅ Logged: {key.replace('_', ' ').title()}", ephemeral=True)
        await log_action(f"{interaction.user.mention} performed {key.replace('_', ' ').title()} at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
        await update_leaderboard()

# Leaderboard updater
async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return
    leaderboard_lines = ["📊 **Work Leaderboard**\n"]
    for user_id, data in work_data.items():
        total_money = (
            data["car_parts"] * PRICE_CAR_PART +
            data["bike_parts"] * PRICE_BIKE_PART +
            data["car_upgrades"] * PRICE_CAR_UPGRADE +
            data["bike_upgrades"] * PRICE_BIKE_UPGRADE +
            data["engine_upgrades"] * PRICE_ENGINE_UPGRADE
        )
        leaderboard_lines.append(
            f"<@{user_id}> - 💸 £{total_money:,} | ⏱️ {format_duration(data['total_time'])}"
        )

    leaderboard_text = "\n".join(leaderboard_lines) or "*No data yet.*"

    async for msg in channel.history(limit=10):
        if msg.author == bot.user and msg.content.startswith("📊 **Work Leaderboard**"):
            await msg.edit(content=leaderboard_text)
            return

    await channel.send(leaderboard_text)

# Start panel
async def panel_message_edit(view):
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        async for msg in panel_channel.history(limit=5):
            if msg.author == bot.user and msg.components:
                await msg.edit(view=view)
                return
        await panel_channel.send("📋 **Work Tracker Panel**", view=view)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    await panel_message_edit(WorkPanel())
    await update_leaderboard()

bot.run(TOKEN)
