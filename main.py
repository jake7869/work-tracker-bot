import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
from collections import defaultdict

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# CONFIG
PANEL_CHANNEL_ID = 1344409201123786758
LOG_CHANNEL_ID = 1390028891791298731
LEADERBOARD_CHANNEL_ID = 1364065995408281651
ADMIN_ROLE_ID = 1391785348262264925

# Pricing
ACTION_PRICES = {
    "car_part": 50000,
    "bike_part": 50000,
    "car_upgrade": 850000,
    "bike_upgrade": 300000,
    "engine_upgrade": 500000
}

# Data
work_data = defaultdict(lambda: {
    "clocked_in": False,
    "last_clock_in": None,
    "total_time": timedelta(),
    "car_parts": 0,
    "bike_parts": 0,
    "car_upgrades": 0,
    "bike_upgrades": 0,
    "engine_upgrades": 0
})

current_panel_message = None
current_leaderboard_message = None

# Util functions
def format_time(seconds):
    return str(timedelta(seconds=int(seconds)))

def get_leaderboard_embed():
    embed = discord.Embed(title="📊 Work Leaderboard", color=discord.Color.gold())
    if not work_data:
        embed.description = "No data available yet."
        return embed

    for user_id, data in work_data.items():
        total_value = (
            data["car_parts"] * ACTION_PRICES["car_part"] +
            data["bike_parts"] * ACTION_PRICES["bike_part"] +
            data["car_upgrades"] * ACTION_PRICES["car_upgrade"] +
            data["bike_upgrades"] * ACTION_PRICES["bike_upgrade"] +
            data["engine_upgrades"] * ACTION_PRICES["engine_upgrade"]
        )
        user_display = f"<@{user_id}>"
        stats = (
            f"**Time:** {format_time(data['total_time'].total_seconds())}\n"
            f"**Car Parts:** {data['car_parts']}\n"
            f"**Bike Parts:** {data['bike_parts']}\n"
            f"**Car Upgrades:** {data['car_upgrades']}\n"
            f"**Bike Upgrades:** {data['bike_upgrades']}\n"
            f"**Engine Upgrades:** {data['engine_upgrades']}\n"
            f"**Total Earned:** £{total_value:,}"
        )
        embed.add_field(name=user_display, value=stats, inline=False)
    return embed

async def log_action(message: str):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(message)

# View & Buttons
class WorkView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.green, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, _):
        user_id = interaction.user.id
        data = work_data[user_id]
        if data["clocked_in"]:
            await interaction.response.send_message("You're already clocked in!", ephemeral=True)
            return
        data["clocked_in"] = True
        data["last_clock_in"] = datetime.utcnow()
        await interaction.response.send_message("You clocked in.", ephemeral=True)
        await log_action(f"📝 {interaction.user.mention} clocked in at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.red, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, _):
        user_id = interaction.user.id
        data = work_data[user_id]
        if not data["clocked_in"]:
            await interaction.response.send_message("You're not clocked in!", ephemeral=True)
            return
        elapsed = datetime.utcnow() - data["last_clock_in"]
        data["total_time"] += elapsed
        data["clocked_in"] = False
        data["last_clock_in"] = None
        await interaction.response.send_message("You clocked out.", ephemeral=True)
        await log_action(f"📝 {interaction.user.mention} clocked out at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

    async def handle_action(self, interaction, field_name, label):
        user_id = interaction.user.id
        data = work_data[user_id]
        if not data["clocked_in"]:
            await interaction.response.send_message("You must clock in first!", ephemeral=True)
            return
        data[field_name] += 1
        await interaction.response.send_message(f"{label} recorded.", ephemeral=True)
        await log_action(f"📝 {interaction.user.mention} completed {label} at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
        await update_leaderboard()

    @discord.ui.button(label="Car Part", style=discord.ButtonStyle.blurple, custom_id="car_part")
    async def car_part(self, interaction: discord.Interaction, _):
        await self.handle_action(interaction, "car_parts", "Car Part")

    @discord.ui.button(label="Bike Part", style=discord.ButtonStyle.blurple, custom_id="bike_part")
    async def bike_part(self, interaction: discord.Interaction, _):
        await self.handle_action(interaction, "bike_parts", "Bike Part")

    @discord.ui.button(label="Car Upgrade", style=discord.ButtonStyle.gray, custom_id="car_upgrade")
    async def car_upgrade(self, interaction: discord.Interaction, _):
        await self.handle_action(interaction, "car_upgrades", "Car Upgrade")

    @discord.ui.button(label="Bike Upgrade", style=discord.ButtonStyle.gray, custom_id="bike_upgrade")
    async def bike_upgrade(self, interaction: discord.Interaction, _):
        await self.handle_action(interaction, "bike_upgrades", "Bike Upgrade")

    @discord.ui.button(label="Engine Upgrade", style=discord.ButtonStyle.gray, custom_id="engine_upgrade")
    async def engine_upgrade(self, interaction: discord.Interaction, _):
        await self.handle_action(interaction, "engine_upgrades", "Engine Upgrade")

    @discord.ui.button(label="Reset Leaderboard", style=discord.ButtonStyle.red, custom_id="reset_leaderboard")
    async def reset_leaderboard(self, interaction: discord.Interaction, _):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("You do not have permission to reset the leaderboard.", ephemeral=True)
            return
        work_data.clear()
        await interaction.response.send_message("Leaderboard has been reset.", ephemeral=True)
        await log_action(f"🧹 {interaction.user.mention} reset the leaderboard at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
        await update_leaderboard()

# Panel posting and updates
async def update_panel():
    global current_panel_message
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if not channel:
        print("Panel channel not found.")
        return
    if current_panel_message:
        try:
            await current_panel_message.delete()
        except:
            pass
    current_panel_message = await channel.send("**Work Tracker Panel**", view=WorkView())

async def update_leaderboard():
    global current_leaderboard_message
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return
    embed = get_leaderboard_embed()
    if current_leaderboard_message:
        try:
            await current_leaderboard_message.edit(embed=embed)
            return
        except:
            pass
    current_leaderboard_message = await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await tree.sync()
    await update_panel()
    await update_leaderboard()

# Run bot
bot.run(os.getenv("DISCORD_TOKEN"))
