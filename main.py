import discord
from discord.ext import commands
from discord import app_commands
import os
from datetime import datetime, timedelta
from collections import defaultdict

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

work_data = defaultdict(lambda: {
    "clocked_in": False,
    "last_clock_in": None,
    "car": 0,
    "bike": 0,
    "engine": 0,
    "car_full": 0,
    "bike_full": 0,
    "earnings": 0,
    "total_time": 0
})

ADMIN_ROLE_ID = 1391785348262264925
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))

PRICE_CONFIG = {
    "car": 50000,
    "bike": 50000,
    "engine": 500000,
    "car_full": 850000,
    "bike_full": 300000
}

class WorkPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You are already clocked in.", ephemeral=True)
        else:
            work_data[user_id]["clocked_in"] = True
            work_data[user_id]["last_clock_in"] = datetime.utcnow()
            await interaction.response.send_message("You clocked in!", ephemeral=True)
            await log_action(f"{interaction.user.mention} Clocked In.")

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if not work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You are not clocked in.", ephemeral=True)
        else:
            start = work_data[user_id]["last_clock_in"]
            duration = (datetime.utcnow() - start).total_seconds()
            work_data[user_id]["total_time"] += duration
            work_data[user_id]["clocked_in"] = False
            work_data[user_id]["last_clock_in"] = None
            await interaction.response.send_message("You clocked out!", ephemeral=True)
            await log_action(f"{interaction.user.mention} Clocked Out. (+{int(duration)}s)")

    async def handle_action(self, interaction, action):
        user_id = str(interaction.user.id)
        if not work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You must clock in first.", ephemeral=True)
            return
        work_data[user_id][action] += 1
        work_data[user_id]["earnings"] += PRICE_CONFIG[action]
        await interaction.response.send_message(f"{action.replace('_',' ').title()} recorded.", ephemeral=True)
        await log_action(f"{interaction.user.mention} performed {action.replace('_', ' ').title()}.")
        await update_leaderboard()

    @discord.ui.button(label="Car Part", style=discord.ButtonStyle.primary, custom_id="car")
    async def upgrade_car(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car")

    @discord.ui.button(label="Bike Part", style=discord.ButtonStyle.primary, custom_id="bike")
    async def upgrade_bike(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "bike")

    @discord.ui.button(label="Engine Upgrade", style=discord.ButtonStyle.primary, custom_id="engine")
    async def upgrade_engine(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "engine")

    @discord.ui.button(label="Full Car Upgrade", style=discord.ButtonStyle.secondary, custom_id="car_full")
    async def full_car_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car_full")

    @discord.ui.button(label="Full Bike Upgrade", style=discord.ButtonStyle.secondary, custom_id="bike_full")
    async def full_bike_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "bike_full")

async def log_action(message):
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
        try:
            user = await bot.fetch_user(int(user_id))
            user_name = user.name
        except:
            user_name = f"<@{user_id}>"

        time_str = str(timedelta(seconds=int(data["total_time"])))
        embed.add_field(
            name=user_name,
            value=(
                f"🚗 Car: {data['car']} | 🛵 Bike: {data['bike']}\n"
                f"🛠️ Engine: {data['engine']} | 🚙 Car Full: {data['car_full']} | 🏍️ Bike Full: {data['bike_full']}\n"
                f"💳 Earnings: £{data['earnings']:,}\n"
                f"⏱️ Time Clocked: {time_str}"
            ),
            inline=False
        )

    history = [msg async for msg in channel.history(limit=5)]
    for msg in history:
        if msg.author == bot.user:
            await msg.delete()

    await channel.send(embed=embed)

@bot.tree.command(name="set_clock")
@app_commands.describe(member="Who to set", state="on or off")
async def set_clock(interaction: discord.Interaction, member: discord.Member, state: str):
    if not has_admin_role(interaction.user):
        await interaction.response.send_message("You are not authorized.", ephemeral=True)
        return

    user_id = str(member.id)
    if state.lower() == "on":
        work_data[user_id]["clocked_in"] = True
        work_data[user_id]["last_clock_in"] = datetime.utcnow()
    else:
        if work_data[user_id]["clocked_in"] and work_data[user_id]["last_clock_in"]:
            duration = (datetime.utcnow() - work_data[user_id]["last_clock_in"]).total_seconds()
            work_data[user_id]["total_time"] += duration
        work_data[user_id]["clocked_in"] = False
        work_data[user_id]["last_clock_in"] = None

    await interaction.response.send_message(f"{member.display_name} set clock {state.upper()}", ephemeral=True)
    await log_action(f"{interaction.user.mention} set clock {state.upper()} for {member.mention}")
    await update_leaderboard()

@bot.tree.command(name="remove_parts")
@app_commands.describe(member="Who to remove from", field="Which field to clear")
async def remove_parts(interaction: discord.Interaction, member: discord.Member, field: str):
    if not has_admin_role(interaction.user):
        await interaction.response.send_message("You are not authorized.", ephemeral=True)
        return

    user_id = str(member.id)
    if field not in work_data[user_id]:
        await interaction.response.send_message("Invalid field.", ephemeral=True)
        return

    removed_value = work_data[user_id][field]
    work_data[user_id][field] = 0
    await interaction.response.send_message(f"Removed {field} ({removed_value}) from {member.display_name}", ephemeral=True)
    await log_action(f"{interaction.user.mention} cleared {field} from {member.mention}")
    await update_leaderboard()

@bot.tree.command(name="remove_time")
@app_commands.describe(member="Who to remove time from", seconds="How many seconds to remove")
async def remove_time(interaction: discord.Interaction, member: discord.Member, seconds: int):
    if not has_admin_role(interaction.user):
        await interaction.response.send_message("You are not authorized.", ephemeral=True)
        return

    user_id = str(member.id)
    work_data[user_id]["total_time"] = max(0, work_data[user_id]["total_time"] - seconds)
    await interaction.response.send_message(f"Removed {seconds} seconds from {member.display_name}'s total time", ephemeral=True)
    await log_action(f"{interaction.user.mention} removed {seconds}s from {member.mention}")
    await update_leaderboard()

def has_admin_role(user: discord.Member) -> bool:
    return any(role.id == ADMIN_ROLE_ID for role in user.roles)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.add_view(WorkPanel())
    try:
        await bot.tree.sync()
        print("Synced commands.")
    except Exception as e:
        print(f"Sync error: {e}")

    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        async for msg in panel_channel.history(limit=5):
            if msg.author == bot.user:
                await msg.delete()
        await panel_channel.send("**Work Panel**", view=WorkPanel())
        await update_leaderboard()

bot.run(DISCORD_BOT_TOKEN)
