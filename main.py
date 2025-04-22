
import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import json
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Environment variable loading
def get_env_var(name, required=True, is_int=False):
    value = os.getenv(name)
    if value is None:
        if required:
            print(f"[ERROR] Missing environment variable: {name}")
        return None
    try:
        return int(value) if is_int else value
    except ValueError:
        print(f"[ERROR] Environment variable {name} should be int.")
        return None

DISCORD_BOT_TOKEN = get_env_var("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = get_env_var("PANEL_CHANNEL_ID", is_int=True)
LOG_CHANNEL_ID = get_env_var("LOG_CHANNEL_ID", is_int=True)
LEADERBOARD_CHANNEL_ID = get_env_var("LEADERBOARD_CHANNEL_ID", is_int=True)
BACKUP_CHANNEL_ID = get_env_var("BACKUP_CHANNEL_ID", is_int=True)

if not all([DISCORD_BOT_TOKEN, PANEL_CHANNEL_ID, LOG_CHANNEL_ID, LEADERBOARD_CHANNEL_ID, BACKUP_CHANNEL_ID]):
    raise ValueError("One or more environment variables are not set correctly.")

# Data storage
DATA_FILE = "leaderboard.json"
CLOCK_FILE = "clocked_in.json"

def load_json(file):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return {}

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

leaderboard = load_json(DATA_FILE)
clocked_in = load_json(CLOCK_FILE)

def get_price(action):
    if action in ["car", "bike", "car_part", "bike_part"]:
        return 50000
    elif action == "engine":
        return 500000
    elif action == "car_full":
        return 850000
    elif action == "bike_full":
        return 300000
    return 0

def ensure_user_data(user_id):
    if str(user_id) not in leaderboard:
        leaderboard[str(user_id)] = {
            "car": 0, "bike": 0, "car_part": 0, "bike_part": 0, "engine": 0,
            "car_full": 0, "bike_full": 0, "earnings": 0, "clocked_time": 0
        }

class WorkPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def record_action(self, user, action, interaction):
        uid = str(user.id)
        if uid not in clocked_in:
            await interaction.response.send_message("You need to clock in first!", ephemeral=True)
            return
        ensure_user_data(uid)
        leaderboard[uid][action] += 1
        leaderboard[uid]["earnings"] += get_price(action)
        save_json(DATA_FILE, leaderboard)
        await interaction.response.send_message(f"{action.replace('_', ' ').capitalize()} recorded!", ephemeral=True)
        await update_leaderboard()

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        clocked_in[str(interaction.user.id)] = datetime.utcnow().isoformat()
        save_json(CLOCK_FILE, clocked_in)
        await interaction.response.send_message("You clocked in!", ephemeral=True)

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid in clocked_in:
            start = datetime.fromisoformat(clocked_in[uid])
            duration = (datetime.utcnow() - start).total_seconds()
            ensure_user_data(uid)
            leaderboard[uid]["clocked_time"] += duration
            del clocked_in[uid]
            save_json(CLOCK_FILE, clocked_in)
            save_json(DATA_FILE, leaderboard)
            await interaction.response.send_message("You clocked out!", ephemeral=True)
            await update_leaderboard()

    @discord.ui.button(label="Car Full Upgrade", style=discord.ButtonStyle.primary, custom_id="car_full")
    async def car_full(self, interaction, button):
        await self.record_action(interaction.user, "car_full", interaction)

    @discord.ui.button(label="Bike Full Upgrade", style=discord.ButtonStyle.primary, custom_id="bike_full")
    async def bike_full(self, interaction, button):
        await self.record_action(interaction.user, "bike_full", interaction)

    @discord.ui.button(label="Car Part", style=discord.ButtonStyle.secondary, custom_id="car_part")
    async def car_part(self, interaction, button):
        await self.record_action(interaction.user, "car_part", interaction)

    @discord.ui.button(label="Bike Part", style=discord.ButtonStyle.secondary, custom_id="bike_part")
    async def bike_part(self, interaction, button):
        await self.record_action(interaction.user, "bike_part", interaction)

    @discord.ui.button(label="Engine Upgrade", style=discord.ButtonStyle.secondary, custom_id="engine")
    async def engine(self, interaction, button):
        await self.record_action(interaction.user, "engine", interaction)

async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return
    leaderboard_data = sorted(leaderboard.items(), key=lambda x: x[1]["earnings"], reverse=True)
    embed = discord.Embed(title="🏆 Leaderboard", color=discord.Color.gold())
    for user_id, data in leaderboard_data:
        user = await bot.fetch_user(int(user_id))
        name = user.display_name if user else f"<@{user_id}>"
        total_time = str(timedelta(seconds=int(data["clocked_time"])))
        embed.add_field(
            name=f"{name}",
            value=(
                f"💰 Earnings: £{data['earnings']:,}
"
                f"🕒 Time: {total_time}
"
                f"🚗 Car: {data['car']} | 🏍️ Bike: {data['bike']}
"
                f"🛠️ Car Parts: {data['car_part']} | Bike Parts: {data['bike_part']}
"
                f"⚙️ Engine: {data['engine']} | Car Full: {data['car_full']} | Bike Full: {data['bike_full']}"
            ),
            inline=False
        )
    async for msg in channel.history(limit=5):
        if msg.author == bot.user and msg.embeds:
            await msg.delete()
    await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.add_view(WorkPanel())
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        async for msg in panel_channel.history(limit=50):
            if msg.author == bot.user:
                await msg.delete()
        await panel_channel.send("**Work Panel**", view=WorkPanel())
    await update_leaderboard()

bot.run(DISCORD_BOT_TOKEN)
