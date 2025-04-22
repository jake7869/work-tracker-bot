
import discord
from discord.ext import commands
from discord import app_commands  # <-- New import
import os

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SHIFT_LOG_CHANNEL_ID = int(os.getenv("SHIFT_LOG_CHANNEL_ID", 0))
SERVICE_LOG_CHANNEL_ID = int(os.getenv("SERVICE_LOG_CHANNEL_ID", 0))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
tree = app_commands.CommandTree(bot)  # <-- New line

@bot.event
async def on_ready():
    await tree.sync()  # <-- New line to register slash commands
    print(f"✅ Logged in as {bot.user}")

# Command: Clock In
@bot.command()
async def clockin(ctx):
    if SHIFT_LOG_CHANNEL_ID:
        channel = bot.get_channel(SHIFT_LOG_CHANNEL_ID)
        await channel.send(f"✅ Clock In = {ctx.author.mention}")
        await ctx.send("You are now clocked in 🕒")

# Command: Clock Out
@bot.command()
async def clockout(ctx):
    if SHIFT_LOG_CHANNEL_ID:
        channel = bot.get_channel(SHIFT_LOG_CHANNEL_ID)
        await channel.send(f"❌ Clock Out = {ctx.author.mention}")
        await ctx.send("You are now clocked out 🕒")

# Command: Log service
@bot.command()
async def service(ctx, type: str, amount: int):
    if SERVICE_LOG_CHANNEL_ID:
        channel = bot.get_channel(SERVICE_LOG_CHANNEL_ID)
        await channel.send(f"🔧 {ctx.author.mention} completed **{amount}** `{type}`")
        await ctx.send(f"Service recorded: {amount} {type}.")

# SLASH COMMAND: Panel
@tree.command(name="panel", description="Display the work tracker panel")
async def panel(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🛠️ **Work Tracker Panel**\nUse `/clockin`, `/clockout`, or `/service` to log your activity."
    )

bot.run(TOKEN)
