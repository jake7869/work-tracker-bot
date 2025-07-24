import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
from datetime import datetime, timedelta

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# CHANNELS AND ROLES
PANEL_CHANNEL_ID = 1344409201123786758
LOG_CHANNEL_ID = 1390028891791298731
LEADERBOARD_CHANNEL_ID = 1364065995408281651
ADMIN_ROLE_ID = 1391785348262264925

# PRICES
PRICES = {
    "car_parts": 50000,
    "bike_parts": 50000,
    "car_upgrades": 850000,
    "bike_upgrades": 300000,
    "engine_upgrades": 500000
}

# TRACKING DICTIONARY
user_data = {}
clocked_in_users = {}

def format_time(seconds):
    return str(timedelta(seconds=int(seconds)))

def get_status_icon(user_id):
    return "<:5264greensiren:>" if user_id in clocked_in_users else ":red_siren:"

# BUTTONS
class WorkButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button("Clock In", "clock_in", discord.ButtonStyle.success))
        self.add_item(Button("Clock Out", "clock_out", discord.ButtonStyle.danger))
        self.add_item(Button("Car Part", "car_part", discord.ButtonStyle.primary))
        self.add_item(Button("Bike Part", "bike_part", discord.ButtonStyle.primary))
        self.add_item(Button("Car Full Upgrade", "car_upgrade", discord.ButtonStyle.secondary))
        self.add_item(Button("Bike Full Upgrade", "bike_upgrade", discord.ButtonStyle.secondary))
        self.add_item(Button("Engine Upgrade", "engine_upgrade", discord.ButtonStyle.secondary))
        self.add_item(Button("Reset Leaderboard", "reset_leaderboard", discord.ButtonStyle.danger))
        self.add_item(Button("Refresh Leaderboard", "refresh_leaderboard", discord.ButtonStyle.primary))
        self.add_item(AdminDropdown())

class Button(discord.ui.Button):
    def __init__(self, label, custom_id, style):
        super().__init__(label=label, custom_id=custom_id, style=style)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        now = datetime.utcnow()

        if self.custom_id == "clock_in":
            clocked_in_users[user.id] = now
            await log_action(f"{user.mention} clocked in at {now}")
            await interaction.response.send_message("You are now clocked in.", ephemeral=True)

        elif self.custom_id == "clock_out":
            if user.id in clocked_in_users:
                start_time = clocked_in_users.pop(user.id)
                duration = (now - start_time).total_seconds()
                user_data.setdefault(user.id, {}).setdefault("time", 0)
                user_data[user.id]["time"] += duration
                await log_action(f"{user.mention} clocked out at {now} (Duration: {format_time(duration)})")
                await interaction.response.send_message("You are now clocked out.", ephemeral=True)
            else:
                await interaction.response.send_message("You are not clocked in.", ephemeral=True)

        elif self.custom_id.startswith("car_part"):
            await increment_task(interaction, user, "car_parts", now, "Car Part")

        elif self.custom_id.startswith("bike_part"):
            await increment_task(interaction, user, "bike_parts", now, "Bike Part")

        elif self.custom_id.startswith("car_upgrade"):
            await increment_task(interaction, user, "car_upgrades", now, "Car Full Upgrade")

        elif self.custom_id.startswith("bike_upgrade"):
            await increment_task(interaction, user, "bike_upgrades", now, "Bike Full Upgrade")

        elif self.custom_id.startswith("engine_upgrade"):
            await increment_task(interaction, user, "engine_upgrades", now, "Engine Upgrade")

        elif self.custom_id == "reset_leaderboard":
            if ADMIN_ROLE_ID in [role.id for role in user.roles]:
                user_data.clear()
                clocked_in_users.clear()
                await log_action(f"{user.mention} reset the leaderboard.")
                await update_leaderboard()
                await interaction.response.send_message("Leaderboard has been reset.", ephemeral=True)
            else:
                await interaction.response.send_message("You don't have permission to do that.", ephemeral=True)

        elif self.custom_id == "refresh_leaderboard":
            await update_leaderboard()
            await interaction.response.send_message("Leaderboard refreshed.", ephemeral=True)

async def increment_task(interaction, user, field, now, label):
    if user.id not in clocked_in_users:
        await interaction.response.send_message("You must clock in first!", ephemeral=True)
        return
    user_data.setdefault(user.id, {}).setdefault(field, 0)
    user_data[user.id][field] += 1
    await log_action(f"{user.mention} completed {label} at {now}")
    await update_leaderboard()
    await interaction.response.send_message(f"{label} logged!", ephemeral=True)

# LOGGING
async def log_action(message):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"📝 {message}")

# LEADERBOARD
async def update_leaderboard():
    leaderboard_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not leaderboard_channel:
        return

    leaderboard_text = "**📊 Work Leaderboard**\n"
    total_earned = 0

    sorted_users = sorted(user_data.items(), key=lambda x: sum([
        x[1].get("car_parts", 0),
        x[1].get("bike_parts", 0),
        x[1].get("car_upgrades", 0),
        x[1].get("bike_upgrades", 0),
        x[1].get("engine_upgrades", 0)
    ]), reverse=True)

    for user_id, data in sorted_users:
        user = await bot.fetch_user(user_id)
        if not user:
            continue
        earnings = (
            data.get("car_parts", 0) * PRICES["car_parts"] +
            data.get("bike_parts", 0) * PRICES["bike_parts"] +
            data.get("car_upgrades", 0) * PRICES["car_upgrades"] +
            data.get("bike_upgrades", 0) * PRICES["bike_upgrades"] +
            data.get("engine_upgrades", 0) * PRICES["engine_upgrades"]
        )
        total_earned += earnings

        status_icon = get_status_icon(user_id)
        leaderboard_text += (
            f"{status_icon} **{user.name}**\n"
            f"Time: {format_time(data.get('time', 0))}\n"
            f"Car Parts: {data.get('car_parts', 0)}\n"
            f"Bike Parts: {data.get('bike_parts', 0)}\n"
            f"Car Upgrades: {data.get('car_upgrades', 0)}\n"
            f"Bike Upgrades: {data.get('bike_upgrades', 0)}\n"
            f"Engine Upgrades: {data.get('engine_upgrades', 0)}\n"
            f"**Total Earned:** £{earnings:,}\n\n"
        )

    leaderboard_text += f"💰 **Total Earned:** £{total_earned:,}"
    messages = [m async for m in leaderboard_channel.history(limit=10)]
    if messages:
        await messages[0].edit(content=leaderboard_text)
    else:
        await leaderboard_channel.send(leaderboard_text)

# ADMIN DROPDOWN
class AdminDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Force Clock Out", value="force_clockout"),
            discord.SelectOption(label="Remove Car Part", value="remove_car_parts"),
            discord.SelectOption(label="Remove Car Upgrade", value="remove_car_upgrades"),
            discord.SelectOption(label="Remove Engine Upgrade", value="remove_engine_upgrades"),
            discord.SelectOption(label="Remove Time", value="remove_time")
        ]
        super().__init__(placeholder="Admin Controls", options=options, min_values=1, max_values=1, custom_id="admin_dropdown")

    async def callback(self, interaction: discord.Interaction):
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("You're not authorized.", ephemeral=True)
            return
        await interaction.response.send_modal(AdminActionModal(self.values[0]))

class AdminActionModal(discord.ui.Modal, title="Admin Action"):
    def __init__(self, action):
        super().__init__()
        self.action = action
        self.user_id = discord.ui.TextInput(label="User ID", placeholder="Enter user ID", required=True)
        self.amount = discord.ui.TextInput(label="Amount", placeholder="Number to remove (for time in seconds)", required=True)
        self.add_item(self.user_id)
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_id.value)
            amt = int(self.amount.value)
            user_data.setdefault(user_id, {})

            if self.action == "force_clockout":
                clocked_in_users.pop(user_id, None)
                await log_action(f"<@{user_id}> was force-clocked out by {interaction.user.mention}")
            elif self.action == "remove_car_parts":
                user_data[user_id]["car_parts"] = max(0, user_data[user_id].get("car_parts", 0) - amt)
                await log_action(f"{interaction.user.mention} removed {amt} Car Parts from <@{user_id}>")
            elif self.action == "remove_car_upgrades":
                user_data[user_id]["car_upgrades"] = max(0, user_data[user_id].get("car_upgrades", 0) - amt)
                await log_action(f"{interaction.user.mention} removed {amt} Car Upgrades from <@{user_id}>")
            elif self.action == "remove_engine_upgrades":
                user_data[user_id]["engine_upgrades"] = max(0, user_data[user_id].get("engine_upgrades", 0) - amt)
                await log_action(f"{interaction.user.mention} removed {amt} Engine Upgrades from <@{user_id}>")
            elif self.action == "remove_time":
                user_data[user_id]["time"] = max(0, user_data[user_id].get("time", 0) - amt)
                await log_action(f"{interaction.user.mention} removed {format_time(amt)} from <@{user_id}>'s clocked time")

            await update_leaderboard()
            await interaction.response.send_message("Admin action complete.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

# STARTUP
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        channel = bot.get_channel(PANEL_CHANNEL_ID)
        await channel.send("**Work Tracker Panel**", view=WorkButtons())
        await update_leaderboard()
    except Exception as e:
        print(f"Error in on_ready: {e}")

bot.run(os.getenv("DISCORD_TOKEN"))
