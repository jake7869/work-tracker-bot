
import discord
from discord.ext import commands
from discord import app_commands, ui
import os

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SHIFT_LOG_CHANNEL_ID = int(os.getenv("SHIFT_LOG_CHANNEL_ID"))
SERVICE_LOG_CHANNEL_ID = int(os.getenv("SERVICE_LOG_CHANNEL_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

tally = {
    "clock_in": 0,
    "clock_out": 0,
    "car_upgrade": 0,
    "bike_upgrade": 0,
    "car_part": 0,
    "bike_part": 0
}

class WorkLoggerView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="🟢 Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: ui.Button):
        tally["clock_in"] += 1
        await interaction.response.send_message("✅ Clocked in!", ephemeral=True)
        channel = bot.get_channel(SHIFT_LOG_CHANNEL_ID)
        await channel.send(f"✅ {interaction.user.mention} clocked in.")

    @ui.button(label="🔴 Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: ui.Button):
        tally["clock_out"] += 1
        await interaction.response.send_message("❌ Clocked out!", ephemeral=True)
        channel = bot.get_channel(SHIFT_LOG_CHANNEL_ID)
        await channel.send(f"❌ {interaction.user.mention} clocked out.")

    @ui.button(label="🚗 Car Upgrade", style=discord.ButtonStyle.primary, custom_id="car_upgrade")
    async def car_upgrade(self, interaction: discord.Interaction, button: ui.Button):
        tally["car_upgrade"] += 1
        await interaction.response.send_message("🔧 Car upgrade logged.", ephemeral=True)
        channel = bot.get_channel(SERVICE_LOG_CHANNEL_ID)
        await channel.send(f"🔧 {interaction.user.mention} completed a **car full upgrade**.")

    @ui.button(label="🏍️ Bike Upgrade", style=discord.ButtonStyle.primary, custom_id="bike_upgrade")
    async def bike_upgrade(self, interaction: discord.Interaction, button: ui.Button):
        tally["bike_upgrade"] += 1
        await interaction.response.send_message("🏍️ Bike upgrade logged.", ephemeral=True)
        channel = bot.get_channel(SERVICE_LOG_CHANNEL_ID)
        await channel.send(f"🔧 {interaction.user.mention} completed a **bike full upgrade**.")

    @ui.button(label="🚘 Car Part", style=discord.ButtonStyle.secondary, custom_id="car_part")
    async def car_part(self, interaction: discord.Interaction, button: ui.Button):
        tally["car_part"] += 1
        await interaction.response.send_message("🚘 Car part logged.", ephemeral=True)
        channel = bot.get_channel(SERVICE_LOG_CHANNEL_ID)
        await channel.send(f"🔩 {interaction.user.mention} installed a **car part**.")

    @ui.button(label="🏍️ Bike Part", style=discord.ButtonStyle.secondary, custom_id="bike_part")
    async def bike_part(self, interaction: discord.Interaction, button: ui.Button):
        tally["bike_part"] += 1
        await interaction.response.send_message("🏍️ Bike part logged.", ephemeral=True)
        channel = bot.get_channel(SERVICE_LOG_CHANNEL_ID)
        await channel.send(f"🔩 {interaction.user.mention} installed a **bike part**.")

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    bot.tree.add_command(post_panel)
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(e)

@bot.tree.command(name="postpanel", description="Post the permanent work logger panel")
async def post_panel(interaction: discord.Interaction):
    embed = discord.Embed(title="🛠️ Work Activity Tracker", description="Click a button to log your work.", color=0x00ff99)
    await interaction.channel.send(embed=embed, view=WorkLoggerView())
    await interaction.response.send_message("✅ Panel posted!", ephemeral=True)

bot.run(TOKEN)
