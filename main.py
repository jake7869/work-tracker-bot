
import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import json

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
BACKUP_CHANNEL_ID = int(os.getenv("BACKUP_CHANNEL_ID"))

work_data = {}

def log_work(user_id, action_type, timestamp):
    if user_id not in work_data:
        work_data[user_id] = {
            "clocked_in": None,
            "car": 0,
            "bike": 0,
            "engine": 0,
            "car_full": 0,
            "bike_full": 0,
            "earnings": 0,
            "total_time": 0
        }

    if action_type == "clock_in":
        work_data[user_id]["clocked_in"] = timestamp
    elif action_type == "clock_out":
        if work_data[user_id]["clocked_in"]:
            duration = (timestamp - work_data[user_id]["clocked_in"]).total_seconds()
            work_data[user_id]["total_time"] += duration
            work_data[user_id]["clocked_in"] = None
    else:
        if work_data[user_id]["clocked_in"]:
            if action_type == "car":
                work_data[user_id]["car"] += 1
                work_data[user_id]["earnings"] += 50000
            elif action_type == "bike":
                work_data[user_id]["bike"] += 1
                work_data[user_id]["earnings"] += 50000
            elif action_type == "engine":
                work_data[user_id]["engine"] += 1
                work_data[user_id]["earnings"] += 500000
            elif action_type == "car_full":
                work_data[user_id]["car_full"] += 1
                work_data[user_id]["earnings"] += 850000
            elif action_type == "bike_full":
                work_data[user_id]["bike_full"] += 1
                work_data[user_id]["earnings"] += 300000

async def log_action(message: str):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(message)

async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return

    leaderboard = sorted(work_data.items(), key=lambda x: x[1]["earnings"], reverse=True)
    embed = discord.Embed(title="🏆 Work Leaderboard", color=discord.Color.gold())

    for user_id, data in leaderboard:
        time_str = str(timedelta(seconds=int(data["total_time"])))
        embed.add_field(
            name=f"<@{user_id}>",
            value=(
                f"🚗 Car: {data['car']} | 🏍️ Bike: {data['bike']}
"
                f"🛠️ Engine: {data['engine']} | 🚗 Car Full: {data['car_full']} | 🏍️ Bike Full: {data['bike_full']}
"
                f"💰 Earnings: £{data['earnings']:,}
"
                f"⏱️ Time Clocked: {time_str}"
            ),
            inline=False
        )

    history = [msg async for msg in channel.history(limit=5)]
    for msg in history:
        if msg.author == bot.user:
            await msg.delete()
    await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await update_leaderboard()

bot.run(DISCORD_BOT_TOKEN)



class WorkPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_action(interaction, "clock_in")

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_action(interaction, "clock_out")

    @discord.ui.button(label="Upgrade Car", style=discord.ButtonStyle.primary, custom_id="car")
    async def upgrade_car(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_action(interaction, "car")

    @discord.ui.button(label="Upgrade Bike", style=discord.ButtonStyle.primary, custom_id="bike")
    async def upgrade_bike(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_action(interaction, "bike")

    @discord.ui.button(label="Install Part", style=discord.ButtonStyle.secondary, custom_id="part")
    async def install_part(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_action(interaction, "part")

    @discord.ui.button(label="Engine Upgrade", style=discord.ButtonStyle.primary, custom_id="engine")
    async def engine_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_action(interaction, "engine")

    @discord.ui.button(label="Full Car Upgrade", style=discord.ButtonStyle.secondary, custom_id="car_full")
    async def full_car_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_action(interaction, "car_full")

    @discord.ui.button(label="Full Bike Upgrade", style=discord.ButtonStyle.secondary, custom_id="bike_full")
    async def full_bike_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_action(interaction, "bike_full")
