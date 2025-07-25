import discord
from discord.ext import commands, tasks
from discord.ui import View, Button, Select
import os
from datetime import datetime, timedelta, timezone
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))

work_data = {}
strike_data = {}
status_message = None
leaderboard_message = None

def format_time(seconds):
    return str(timedelta(seconds=int(seconds)))

def get_status_icon(user_id):
    user = work_data.get(user_id, {})
    return ":green_circle:" if user.get("clocked_in") else ":red_circle:"

async def send_log(message):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(message)

async def send_dm(user, message):
    try:
        await user.send(message)
    except:
        pass

def calculate_earnings(data):
    return (
        data["car_parts"] +
        data["bike_parts"] +
        data["car_upgrades"] +
        data["bike_upgrades"]
    ) * 50000 + data["engine_upgrades"] * 500000

class WorkButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ClockIn())
        self.add_item(ClockOut())
        self.add_item(AddTask("Car Part", "car_parts"))
        self.add_item(AddTask("Bike Part", "bike_parts"))
        self.add_item(AddTask("Car Full Upgrade", "car_upgrades"))
        self.add_item(AddTask("Bike Full Upgrade", "bike_upgrades"))
        self.add_item(AddTask("Engine Upgrade", "engine_upgrades"))
        self.add_item(ResetLeaderboard())
        self.add_item(RefreshLeaderboard())
        self.add_item(AdminDropdown())

class ClockIn(Button):
    def __init__(self):
        super().__init__(label="Clock In", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        user_data = work_data.setdefault(user_id, {
            "clocked_in": False,
            "start_time": None,
            "total_time": 0,
            "car_parts": 0,
            "bike_parts": 0,
            "car_upgrades": 0,
            "bike_upgrades": 0,
            "engine_upgrades": 0
        })

        if user_data["clocked_in"]:
            await interaction.response.send_message("You're already clocked in.", ephemeral=True)
            return

        user_data["clocked_in"] = True
        user_data["start_time"] = datetime.now(timezone.utc)
        await interaction.response.send_message("Clocked in.", ephemeral=True)
        await send_log(f"{interaction.user.mention} clocked in.")

class ClockOut(Button):
    def __init__(self):
        super().__init__(label="Clock Out", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        user_data = work_data.get(user_id)

        if not user_data or not user_data["clocked_in"]:
            await interaction.response.send_message("You're not clocked in.", ephemeral=True)
            return

        elapsed = (datetime.now(timezone.utc) - user_data["start_time"]).total_seconds()
        user_data["total_time"] += elapsed
        user_data["clocked_in"] = False
        user_data["start_time"] = None

        await interaction.response.send_message("Clocked out.", ephemeral=True)
        await send_log(f"{interaction.user.mention} clocked out. Session: {format_time(elapsed)}")

class AddTask(Button):
    def __init__(self, label, field):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.field = field

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        user_data = work_data.get(user_id)

        if not user_data or not user_data["clocked_in"]:
            await interaction.response.send_message("You must be clocked in to do that.", ephemeral=True)
            return

        user_data[self.field] += 1
        await interaction.response.send_message(f"{self.label} logged.", ephemeral=True)
        await send_log(f"{interaction.user.mention} completed task: **{self.label}**")

class ResetLeaderboard(Button):
    def __init__(self):
        super().__init__(label="Reset Leaderboard", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("You do not have permission.", ephemeral=True)
            return

        global work_data, strike_data
        work_data.clear()
        strike_data.clear()
        await interaction.response.send_message("Leaderboard has been reset.", ephemeral=True)
        await send_log(f":warning: {interaction.user.mention} reset the leaderboard.")

class RefreshLeaderboard(Button):
    def __init__(self):
        super().__init__(label="Refresh Leaderboard", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        await update_leaderboard()
        await interaction.response.send_message("Leaderboard refreshed.", ephemeral=True)

class AdminDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Force Clock Out", value="force_clock_out"),
            discord.SelectOption(label="Remove Car Part", value="remove_car_parts"),
            discord.SelectOption(label="Remove Bike Part", value="remove_bike_parts"),
            discord.SelectOption(label="Remove Car Upgrade", value="remove_car_upgrades"),
            discord.SelectOption(label="Remove Bike Upgrade", value="remove_bike_upgrades"),
            discord.SelectOption(label="Remove Engine Upgrade", value="remove_engine_upgrades"),
            discord.SelectOption(label="Remove 1h Time", value="remove_time"),
        ]
        super().__init__(placeholder="Admin Actions", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("You do not have permission.", ephemeral=True)
            return

        await interaction.response.send_message("Select a user to apply action.", ephemeral=True)

class AdminView(View):
    def __init__(self, action, admin):
        super().__init__(timeout=60)
        self.action = action
        self.admin = admin
        self.add_item(UserSelectDropdown(action, admin))

class UserSelectDropdown(Select):
    def __init__(self, action, admin):
        self.action = action
        self.admin = admin
        options = [discord.SelectOption(label=member.name, value=str(member.id)) for member in work_data.keys()]
        super().__init__(placeholder="Choose user", options=options)

    async def callback(self, interaction: discord.Interaction):
        user_id = int(self.values[0])
        user = interaction.guild.get_member(user_id)
        user_data = work_data.get(user_id)

        if not user_data:
            await interaction.response.send_message("User not found.", ephemeral=True)
            return

        if self.action == "force_clock_out":
            if user_data["clocked_in"]:
                elapsed = (datetime.now(timezone.utc) - user_data["start_time"]).total_seconds()
                user_data["total_time"] += elapsed
                user_data["clocked_in"] = False
                user_data["start_time"] = None
                await send_log(f":warning: {user.mention} was force-clocked out by {self.admin.mention}")
        elif self.action.startswith("remove_"):
            field = self.action.replace("remove_", "")
            if field == "time":
                user_data["total_time"] = max(0, user_data["total_time"] - 3600)
                await send_log(f"{self.admin.mention} removed 1h from {user.mention}")
            else:
                user_data[field] = max(0, user_data[field] - 1)
                await send_log(f"{self.admin.mention} removed 1 from {field} for {user.mention}")

        await update_leaderboard()
        await interaction.response.send_message("Action completed.", ephemeral=True)

@tasks.loop(minutes=5)
async def check_clock_ins():
    now = datetime.now(timezone.utc)
    for user_id, data in work_data.items():
        if data.get("clocked_in"):
            start = data.get("start_time")
            if start and (now - start).total_seconds() > 10800:
                user = await bot.fetch_user(user_id)
                if not data.get("warned"):
                    await send_dm(user, "You’ve been clocked in for 3 hours. Reply to this message to stay clocked in.")
                    data["warned"] = True
                    data["warn_time"] = now
                elif (now - data["warn_time"]).total_seconds() > 1800:
                    data["clocked_in"] = False
                    data["total_time"] = max(0, data["total_time"] - 32400)
                    data["start_time"] = None
                    data["warned"] = False
                    strikes = strike_data.setdefault(user_id, 0)
                    strike_data[user_id] = strikes + 1
                    await send_log(f":rotating_light: <@&{ADMIN_ROLE_ID}> {user.mention} was auto clocked out and punished. Strike {strike_data[user_id]}/3")
                    if strike_data[user_id] >= 3:
                        work_data.pop(user_id, None)
                        await send_dm(user, "Your data has been wiped due to repeated clock-in abuse.")
                        await send_log(f":x: <@&{ADMIN_ROLE_ID}> {user.mention}'s data was wiped due to 3 strikes.")

async def update_leaderboard():
    global leaderboard_message
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return

    leaderboard = sorted(work_data.items(), key=lambda x: calculate_earnings(x[1]), reverse=True)
    embed = discord.Embed(title="📊 Work Leaderboard", color=discord.Color.gold())
    total_earned = 0

    for user_id, data in leaderboard:
        user = await bot.fetch_user(user_id)
        icon = get_status_icon(user_id)
        earned = calculate_earnings(data)
        total_earned += earned
        embed.add_field(
            name=f"{icon} {user.name}",
            value=(
                f"Time: {format_time(data['total_time'])}\n"
                f"Car Parts: {data['car_parts']}\n"
                f"Bike Parts: {data['bike_parts']}\n"
                f"Car Full Upgrades: {data['car_upgrades']}\n"
                f"Bike Full Upgrades: {data['bike_upgrades']}\n"
                f"Engine Upgrades: {data['engine_upgrades']}\n"
                f"Total Earned: £{earned:,}"
            ),
            inline=False
        )

    embed.set_footer(text=f"Total Money Earned: £{total_earned:,}")
    if leaderboard_message:
        await leaderboard_message.edit(embed=embed)
    else:
        leaderboard_message = await channel.send(embed=embed)

@bot.event
async def on_ready():
    global status_message
    print(f"Logged in as {bot.user}")
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        status_message = await panel_channel.send("**Work Tracker Panel**", view=WorkButtons())
    await update_leaderboard()
    check_clock_ins.start()

bot.run(TOKEN)
