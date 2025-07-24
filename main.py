import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta, UTC
from collections import defaultdict
import os

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

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ADMIN_ROLE_ID = 1391785348262264925

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
            work_data[user_id]["last_clock_in"] = datetime.now(UTC)
            await interaction.response.send_message("You clocked in!", ephemeral=True)
            await log_action(f"{interaction.user.mention} Clocked In at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}")

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if not work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You are not clocked in.", ephemeral=True)
        else:
            start = work_data[user_id]["last_clock_in"]
            duration = (datetime.now(UTC) - start).total_seconds()
            work_data[user_id]["total_time"] += duration
            work_data[user_id]["clocked_in"] = False
            work_data[user_id]["last_clock_in"] = None
            await interaction.response.send_message("You clocked out!", ephemeral=True)
            await log_action(f"{interaction.user.mention} Clocked Out at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}")

    async def handle_action(self, interaction, action):
        user_id = str(interaction.user.id)
        if not work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You must clock in before performing this action.", ephemeral=True)
            return
        work_data[user_id][action] += 1
        work_data[user_id]["earnings"] += PRICE_CONFIG[action]
        await interaction.response.send_message(f"{action.replace('_', ' ').title()} recorded!", ephemeral=True)
        await log_action(f"{interaction.user.mention} performed {action.replace('_', ' ').title()} at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}")
        await update_leaderboard()

    @discord.ui.button(label="Car Part", style=discord.ButtonStyle.primary, custom_id="car")
    async def upgrade_car(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car")

    @discord.ui.button(label="Bike Part", style=discord.ButtonStyle.primary, custom_id="bike")
    async def upgrade_bike(self, interaction: discord.Interaction, button: discord.ui.Button):
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

    @discord.ui.button(label="🔄 Refresh Leaderboard", style=discord.ButtonStyle.secondary, custom_id="refresh")
    async def refresh_leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard()
        await interaction.response.send_message("Leaderboard refreshed!", ephemeral=True)

    @discord.ui.button(label="⚠️ Reset Leaderboard", style=discord.ButtonStyle.danger, custom_id="reset")
    async def reset_leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to reset the leaderboard.", ephemeral=True)
            return

        confirm_view = ConfirmResetView()
        await interaction.response.send_message("Are you sure you want to reset the leaderboard?", view=confirm_view, ephemeral=True)

class ConfirmResetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="Confirm Reset", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        work_data.clear()
        await update_leaderboard()
        await interaction.response.send_message("Leaderboard has been reset!", ephemeral=True)
        await log_action(f"{interaction.user.mention} reset the leaderboard.")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Reset cancelled.", ephemeral=True)

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
        try:
            user = await bot.fetch_user(int(user_id))
            user_name = user.name
        except:
            user_name = f"<@{user_id}>"

        time_str = str(timedelta(seconds=int(data["total_time"])))
        embed.add_field(
            name=user_name,
            value=(f"🚗 Car: {data['car']} | 🛵 Bike: {data['bike']}\n"
                   f"🛠️ Engine: {data['engine']} | 🚙 Car Full: {data['car_full']} | 🏍️ Bike Full: {data['bike_full']}\n"
                   f"💳 Earnings: £{data['earnings']:,}\n"
                   f"⏱️ Time Clocked: {time_str}"),
            inline=False
        )

    async for msg in channel.history(limit=5):
        if msg.author == bot.user:
            await msg.delete()

    await channel.send(embed=embed, view=WorkPanel())

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print("Failed to sync commands:", e)

    bot.add_view(WorkPanel())
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        async for msg in panel_channel.history(limit=5):
            if msg.author == bot.user:
                await msg.delete()
        await panel_channel.send("**Work Panel**", view=WorkPanel())

    await update_leaderboard()

# ----------------- ADMIN COMMANDS ------------------

@bot.tree.command(name="admin_clock", description="Force clock a user in or out.")
@app_commands.checks.has_role(ADMIN_ROLE_ID)
async def admin_clock(interaction: discord.Interaction, user: discord.User, action: str):
    uid = str(user.id)
    if action.lower() == "in":
        work_data[uid]["clocked_in"] = True
        work_data[uid]["last_clock_in"] = datetime.now(UTC)
        await interaction.response.send_message(f"{user.name} clocked in.")
    elif action.lower() == "out":
        if work_data[uid]["clocked_in"]:
            start = work_data[uid]["last_clock_in"]
            duration = (datetime.now(UTC) - start).total_seconds()
            work_data[uid]["total_time"] += duration
        work_data[uid]["clocked_in"] = False
        work_data[uid]["last_clock_in"] = None
        await interaction.response.send_message(f"{user.name} clocked out.")
    else:
        await interaction.response.send_message("Use 'in' or 'out' for the action.")

@bot.tree.command(name="admin_remove_part", description="Remove part/full/engine upgrades from a user.")
@app_commands.checks.has_role(ADMIN_ROLE_ID)
async def admin_remove_part(interaction: discord.Interaction, user: discord.User, category: str, amount: int):
    uid = str(user.id)
    if category not in work_data[uid]:
        await interaction.response.send_message("Invalid category.")
        return
    work_data[uid][category] = max(0, work_data[uid][category] - amount)
    work_data[uid]["earnings"] = max(0, work_data[uid]["earnings"] - PRICE_CONFIG.get(category, 0) * amount)
    await interaction.response.send_message(f"Removed {amount} from {category} for {user.name}.")
    await update_leaderboard()

@bot.tree.command(name="admin_remove_time", description="Remove time from a user's total clocked in time (in seconds).")
@app_commands.checks.has_role(ADMIN_ROLE_ID)
async def admin_remove_time(interaction: discord.Interaction, user: discord.User, seconds: int):
    uid = str(user.id)
    work_data[uid]["total_time"] = max(0, work_data[uid]["total_time"] - seconds)
    await interaction.response.send_message(f"Removed {seconds} seconds from {user.name}'s total time.")
    await update_leaderboard()

# ---------------------------------------------------

bot.run(DISCORD_BOT_TOKEN)
