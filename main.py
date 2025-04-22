
import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import json

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

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

data_store = "data.json"
clocked_in = {}

# --- UTILS ---
def load_data():
    if not os.path.exists(data_store):
        return {}
    with open(data_store, "r") as f:
        return json.load(f)

def save_data(data):
    with open(data_store, "w") as f:
        json.dump(data, f, indent=2)

def calculate_earnings(user_data):
    prices = {
        "car": 50000,
        "bike": 50000,
        "engine": 500000,
        "car_full": 850000,
        "bike_full": 300000
    }
    total = sum(user_data.get(key, 0) * price for key, price in prices.items())
    return total

# --- UI PANEL ---
class WorkPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update_leaderboard(self):
        data = load_data()
        leaderboard_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if leaderboard_channel:
            sorted_users = sorted(data.items(), key=lambda x: calculate_earnings(x[1]), reverse=True)
            embed = discord.Embed(title="🏆 Leaderboard", color=discord.Color.gold())
            for user_id, stats in sorted_users:
                mention = f"<@{user_id}>"
                earnings = calculate_earnings(stats)
                time_spent = str(timedelta(seconds=stats.get("clocked_time", 0)))
                embed.add_field(
                    name=f"{mention}",
                    value=(
                        f"🚗 Car Parts: {stats.get('car', 0)}
"
                        f"🏍️ Bike Parts: {stats.get('bike', 0)}
"
                        f"🔧 Engine Upgrades: {stats.get('engine', 0)}
"
                        f"🚘 Full Car Upgrades: {stats.get('car_full', 0)}
"
                        f"🏍️ Full Bike Upgrades: {stats.get('bike_full', 0)}
"
                        f"⏱️ Time Clocked In: {time_spent}
"
                        f"💰 Earnings: £{earnings:,}"
                    ),
                    inline=False
                )
            await leaderboard_channel.purge(limit=10)
            await leaderboard_channel.send(embed=embed)

    async def handle_action(self, interaction, action):
        user_id = str(interaction.user.id)
        data = load_data()

        if action == "clock_in":
            clocked_in[user_id] = datetime.utcnow()
            await interaction.response.send_message("⏱️ You clocked in!", ephemeral=True)
            return

        if action == "clock_out":
            if user_id in clocked_in:
                seconds = (datetime.utcnow() - clocked_in[user_id]).total_seconds()
                data.setdefault(user_id, {}).setdefault("clocked_time", 0)
                data[user_id]["clocked_time"] += int(seconds)
                del clocked_in[user_id]
            await interaction.response.send_message("🛑 You clocked out!", ephemeral=True)
            save_data(data)
            return

        if user_id not in clocked_in:
            await interaction.response.send_message("❗You must clock in before performing actions.", ephemeral=True)
            return

        stat_map = {
            "car": "Car Part Installed!",
            "bike": "Bike Part Installed!",
            "engine": "Engine Upgraded!",
            "car_full": "Car Fully Upgraded!",
            "bike_full": "Bike Fully Upgraded!"
        }

        if action in stat_map:
            data.setdefault(user_id, {}).setdefault(action, 0)
            data[user_id][action] += 1
            await interaction.response.send_message(f"{stat_map[action]}", ephemeral=True)
            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"{interaction.user.mention} {stat_map[action]} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            save_data(data)
            await self.update_leaderboard()

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "clock_in")

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "clock_out")

    @discord.ui.button(label="Car Part", style=discord.ButtonStyle.primary, custom_id="car")
    async def car_part(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car")

    @discord.ui.button(label="Bike Part", style=discord.ButtonStyle.primary, custom_id="bike")
    async def bike_part(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "bike")

    @discord.ui.button(label="Engine Upgrade", style=discord.ButtonStyle.primary, custom_id="engine")
    async def engine_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "engine")

    @discord.ui.button(label="Full Car Upgrade", style=discord.ButtonStyle.secondary, custom_id="car_full")
    async def car_full_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car_full")

    @discord.ui.button(label="Full Bike Upgrade", style=discord.ButtonStyle.secondary, custom_id="bike_full")
    async def bike_full_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "bike_full")

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

bot.run(DISCORD_BOT_TOKEN)
