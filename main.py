
import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
BACKUP_CHANNEL_ID = int(os.getenv("BACKUP_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
work_data = {}
clocked_in_users = {}

def log_action(message: str):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        return channel.send(message)

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
                f"🛠 Engine: {data['engine']} | 🚗 Car Full: {data['car_full']} | 🏍️ Bike Full: {data['bike_full']}
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
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        async for msg in panel_channel.history(limit=5):
            if msg.author == bot.user:
                await msg.delete()
        await panel_channel.send("**Work Panel**")

bot.run(DISCORD_BOT_TOKEN)
