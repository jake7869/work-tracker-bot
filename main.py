
# main.py (finalized version with all features)
import discord
from discord.ext import tasks
import os
import asyncio
from datetime import datetime, timedelta
import json

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = discord.Bot(intents=intents)

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
BACKUP_CHANNEL_ID = int(os.getenv("BACKUP_CHANNEL_ID"))

DATA_FILE = "leaderboard_data.json"
SHIFT_FILE = "shift_data.json"

ACTION_PRICES = {
    "car": 50000,
    "bike": 50000,
    "car_part": 50000,
    "bike_part": 50000,
    "engine": 500000,
    "car_full": 850000,
    "bike_full": 300000
}

def load_data(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)

def save_data(data, file):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

def get_display_time(seconds):
    return str(timedelta(seconds=round(seconds)))

class WorkPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "clock_in")

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "clock_out")

    @discord.ui.button(label="Upgrade Car", style=discord.ButtonStyle.primary, custom_id="car")
    async def upgrade_car(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car")

    @discord.ui.button(label="Upgrade Bike", style=discord.ButtonStyle.primary, custom_id="bike")
    async def upgrade_bike(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "bike")

    @discord.ui.button(label="Install Car Part", style=discord.ButtonStyle.secondary, custom_id="car_part")
    async def install_car_part(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car_part")

    @discord.ui.button(label="Install Bike Part", style=discord.ButtonStyle.secondary, custom_id="bike_part")
    async def install_bike_part(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "bike_part")

    @discord.ui.button(label="Engine Upgrade", style=discord.ButtonStyle.primary, custom_id="engine")
    async def engine_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "engine")

    @discord.ui.button(label="Full Car Upgrade", style=discord.ButtonStyle.success, custom_id="car_full")
    async def full_car_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car_full")

    @discord.ui.button(label="Full Bike Upgrade", style=discord.ButtonStyle.success, custom_id="bike_full")
    async def full_bike_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "bike_full")

    async def handle_action(self, interaction, action_type):
        user_id = str(interaction.user.id)
        username = interaction.user.mention
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        shift_data = load_data(SHIFT_FILE)
        if action_type == "clock_in":
            shift_data[user_id] = {"clock_in": datetime.utcnow().timestamp()}
            save_data(shift_data, SHIFT_FILE)
            await interaction.response.send_message("You clocked in!", ephemeral=True)
            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            await log_channel.send(f"{username} Clocked In at {timestamp}")
            return

        if action_type == "clock_out":
            if user_id in shift_data and "clock_in" in shift_data[user_id]:
                duration = datetime.utcnow().timestamp() - shift_data[user_id]["clock_in"]
                leaderboard = load_data(DATA_FILE)
                leaderboard.setdefault(user_id, {"username": username, "time": 0, "earnings": 0})
                leaderboard[user_id]["time"] += duration
                save_data(leaderboard, DATA_FILE)
                shift_data.pop(user_id)
                save_data(shift_data, SHIFT_FILE)
                await interaction.response.send_message("You clocked out!", ephemeral=True)
                log_channel = bot.get_channel(LOG_CHANNEL_ID)
                await log_channel.send(f"{username} Clocked Out at {timestamp}")
            else:
                await interaction.response.send_message("You are not clocked in.", ephemeral=True)
            return

        if user_id not in shift_data:
            await interaction.response.send_message("Please clock in first!", ephemeral=True)
            return

        leaderboard = load_data(DATA_FILE)
        leaderboard.setdefault(user_id, {"username": username, "time": 0, "earnings": 0})
        leaderboard[user_id]["earnings"] += ACTION_PRICES.get(action_type, 0)
        save_data(leaderboard, DATA_FILE)
        await interaction.response.send_message(f"{action_type.replace('_', ' ').title()} logged!", ephemeral=True)
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        await log_channel.send(f"{username} performed {action_type.replace('_', ' ').title()} at {timestamp}")

@tasks.loop(minutes=1)
async def update_leaderboard():
    leaderboard = load_data(DATA_FILE)
    sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1]["earnings"], reverse=True)

    embed = discord.Embed(title="🏆 Leaderboard", color=discord.Color.gold())
    for user_id, data in sorted_lb:
        embed.add_field(name=data["username"], value=f"💰 £{data['earnings']:,} | ⏱️ {get_display_time(data['time'])}", inline=False)

    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if channel:
        async for msg in channel.history(limit=10):
            if msg.author == bot.user:
                await msg.delete()
        await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.add_view(WorkPanel())
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if channel:
        async for msg in channel.history(limit=10):
            if msg.author == bot.user:
                await msg.delete()
        await channel.send("**Work Panel**", view=WorkPanel())
    update_leaderboard.start()

bot.run(DISCORD_BOT_TOKEN)
