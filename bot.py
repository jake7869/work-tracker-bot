
import os
import discord
from discord.ext import commands
from discord import option
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SHIFT_LOG_CHANNEL_ID = int(os.getenv("SHIFT_LOG_CHANNEL_ID", 0))
SERVICE_LOG_CHANNEL_ID = int(os.getenv("SERVICE_LOG_CHANNEL_ID", 0))

bot = discord.Bot(intents=discord.Intents.default())

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print("🔁 Syncing commands...")
    await bot.sync_commands()
    print("✅ Synced slash commands!")

# Slash command: Clock In
@bot.slash_command(name="clockin", description="Clock in for your shift.")
async def clockin(ctx):
    channel = bot.get_channel(SHIFT_LOG_CHANNEL_ID)
    await channel.send(f"✅ Clock In = {ctx.author.mention}")
    await ctx.respond("You are now clocked in! 🟢", ephemeral=True)

# Slash command: Clock Out
@bot.slash_command(name="clockout", description="Clock out from your shift.")
async def clockout(ctx):
    channel = bot.get_channel(SHIFT_LOG_CHANNEL_ID)
    await channel.send(f"❌ Clock Out = {ctx.author.mention}")
    await ctx.respond("You are now clocked out! 🔴", ephemeral=True)

# Slash command: Log service activity
@bot.slash_command(name="service", description="Log a completed service task.")
@option("type", description="The type of service (e.g., Car Upgrade, Bike Parts)")
@option("amount", description="Number of services completed", min_value=1)
async def service(ctx, type: str, amount: int):
    channel = bot.get_channel(SERVICE_LOG_CHANNEL_ID)
    await channel.send(f"🔧 {ctx.author.mention} completed **{amount}** `{type}`")
    await ctx.respond(f"✅ Recorded: {amount} {type}", ephemeral=True)

# Slash command: Panel
@bot.slash_command(name="panel", description="Show the tracker panel.")
async def panel(ctx):
    await ctx.respond("🛠️ **Work Tracker Panel**\nUse `/clockin`, `/clockout`, or `/service` to log work.")

bot.run(TOKEN)
