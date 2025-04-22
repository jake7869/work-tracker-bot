
import discord
from discord.ext import commands, tasks
import os
import json
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
BACKUP_CHANNEL_ID = int(os.getenv("BACKUP_CHANNEL_ID"))

DATA_FILE = "work_data.json"
SHIFT_FILE = "shift_data.json"

PRICES = {
    "car": 50000,
    "bike": 50000,
    "car_full": 850000,
    "bike_full": 300000,
    "engine": 500000
}

work_data = defaultdict(lambda: {
    "car": 0, "bike": 0, "car_full": 0, "bike_full": 0, "engine": 0, "earnings": 0, "clocked_in": False, "clock_in_time": None, "total_time": 0
})

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(work_data, f, indent=2)

def load_data():
    global work_data
    if Path(DATA_FILE).exists():
        with open(DATA_FILE) as f:
            data = json.load(f)
            work_data = defaultdict(lambda: {
                "car": 0, "bike": 0, "car_full": 0, "bike_full": 0, "engine": 0, "earnings": 0, "clocked_in": False, "clock_in_time": None, "total_time": 0
            }, data)

load_data()

class WorkPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def handle_action(self, interaction, action):
        user_id = str(interaction.user.id)
        user_data = work_data[user_id]

        if action == "clock_in":
            if user_data["clocked_in"]:
                await interaction.response.send_message("You're already clocked in!", ephemeral=True)
                return
            user_data["clocked_in"] = True
            user_data["clock_in_time"] = datetime.utcnow().isoformat()
            await interaction.response.send_message("You clocked in!", ephemeral=True)
            await log_action(f"{interaction.user.mention} Clocked In at {datetime.utcnow()}")

        elif action == "clock_out":
            if not user_data["clocked_in"]:
                await interaction.response.send_message("You're not clocked in!", ephemeral=True)
                return
            start = datetime.fromisoformat(user_data["clock_in_time"])
            delta = datetime.utcnow() - start
            user_data["total_time"] += int(delta.total_seconds())
            user_data["clocked_in"] = False
            user_data["clock_in_time"] = None
            await interaction.response.send_message("You clocked out!", ephemeral=True)
            await log_action(f"{interaction.user.mention} Clocked Out at {datetime.utcnow()}")

        elif action in PRICES:
            if not user_data["clocked_in"]:
                await interaction.response.send_message("Please clock in first!", ephemeral=True)
                return
            user_data[action] += 1
            user_data["earnings"] += PRICES[action]
            await interaction.response.send_message(f"{action.replace('_', ' ').capitalize()} recorded!", ephemeral=True)
            await log_action(f"{interaction.user.mention} did {action} at {datetime.utcnow()}")

        save_data()
        await update_leaderboard()

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success)
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "clock_in")

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger)
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "clock_out")

    @discord.ui.button(label="Upgrade Car", style=discord.ButtonStyle.primary)
    async def car(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car")

    @discord.ui.button(label="Upgrade Bike", style=discord.ButtonStyle.primary)
    async def bike(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "bike")

    @discord.ui.button(label="Install Part", style=discord.ButtonStyle.secondary)
    async def part(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "engine")

    @discord.ui.button(label="Full Car Upgrade", style=discord.ButtonStyle.secondary)
    async def car_full(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car_full")

    @discord.ui.button(label="Full Bike Upgrade", style=discord.ButtonStyle.secondary)
    async def bike_full(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "bike_full")


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
        time_str = str(timedelta(seconds=data["total_time"]))
        embed.add_field(
            name=f"<@{user_id}>",
            value=(
                f"🚗 Car: {data['car']} | 🏍️ Bike: {data['bike']}
"
                f"🔧 Engine: {data['engine']} | 🚘 Car Full: {data['car_full']} | 🏍️ Bike Full: {data['bike_full']}
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
    bot.add_view(WorkPanel())

    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        async for msg in panel_channel.history(limit=5):
            if msg.author == bot.user:
                await msg.delete()
        await panel_channel.send("**Work Panel**", view=WorkPanel())

bot.run(DISCORD_BOT_TOKEN)
