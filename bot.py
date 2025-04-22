import discord
from discord.ext import commands
import os

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SHIFT_LOG_CHANNEL_ID = int(os.getenv("SHIFT_LOG_CHANNEL_ID", 0))
SERVICE_LOG_CHANNEL_ID = int(os.getenv("SERVICE_LOG_CHANNEL_ID", 0))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# === Basic Events ===
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# === Basic Commands ===
@bot.command()
async def clockin(ctx):
    if SHIFT_LOG_CHANNEL_ID:
        channel = bot.get_channel(SHIFT_LOG_CHANNEL_ID)
        await channel.send(f"✅ Clock In = {ctx.author.mention}")
        await ctx.send("You are now clocked in 🕒")

@bot.command()
async def clockout(ctx):
    if SHIFT_LOG_CHANNEL_ID:
        channel = bot.get_channel(SHIFT_LOG_CHANNEL_ID)
        await channel.send(f"❌ Clock Out = {ctx.author.mention}")
        await ctx.send("You are now clocked out 🕔")

@bot.command()
async def service(ctx, type: str, amount: int):
    if SERVICE_LOG_CHANNEL_ID:
        channel = bot.get_channel(SERVICE_LOG_CHANNEL_ID)
        await channel.send(f"🔧 {ctx.author.mention} completed **{amount}** `{type}`")
        await ctx.send(f"Service recorded: {amount} {type}")

# === Persistent Panel with Buttons ===
class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clockin_button")
    async def clockin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if SHIFT_LOG_CHANNEL_ID:
            channel = bot.get_channel(SHIFT_LOG_CHANNEL_ID)
            await channel.send(f"✅ Clock In = {interaction.user.mention}")
        await interaction.response.send_message("Clocked in!", ephemeral=True)

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clockout_button")
    async def clockout_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if SHIFT_LOG_CHANNEL_ID:
            channel = bot.get_channel(SHIFT_LOG_CHANNEL_ID)
            await channel.send(f"❌ Clock Out = {interaction.user.mention}")
        await interaction.response.send_message("Clocked out!", ephemeral=True)

@bot.command()
async def panel(ctx):
    view = PanelView()
    await ctx.send("**Shift Panel:**", view=view)

bot.run(TOKEN)
