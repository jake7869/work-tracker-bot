import discord
import asyncio
import os
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
TOKEN = os.getenv("DISCORD_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))

work_data = {}
clock_in_status = {}
strikes = {}

EARNINGS = {
    "Car Part": 50000,
    "Bike Part": 50000,
    "Car Full Upgrade": 850000,
    "Bike Full Upgrade": 300000,
    "Engine Upgrade": 500000
}

class WorkButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ClockInButton())
        self.add_item(ClockOutButton())
        self.add_item(CarPartButton())
        self.add_item(BikePartButton())
        self.add_item(CarUpgradeButton())
        self.add_item(BikeUpgradeButton())
        self.add_item(EngineUpgradeButton())
        self.add_item(ResetLeaderboardButton())
        self.add_item(RefreshLeaderboardButton())
        self.add_item(AdminDropdown())

class ClockInButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Clock In", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if clock_in_status.get(user_id, False):
            await interaction.response.send_message("You're already clocked in.", ephemeral=True)
            return

        clock_in_status[user_id] = True
        work_data.setdefault(user_id, {
            "clocked_in": True,
            "start_time": datetime.now(timezone.utc),
            "total_time": timedelta(),
            "Car Part": 0,
            "Bike Part": 0,
            "Car Full Upgrade": 0,
            "Bike Full Upgrade": 0,
            "Engine Upgrade": 0
        })
        work_data[user_id]["start_time"] = datetime.now(timezone.utc)
        await log_action(interaction.user, "Clocked In")
        await interaction.response.send_message("Clocked in successfully!", ephemeral=True)

class ClockOutButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Clock Out", style=discord.ButtonStyle.danger, row=0)

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if not clock_in_status.get(user_id, False):
            await interaction.response.send_message("You're not clocked in.", ephemeral=True)
            return

        start_time = work_data[user_id]["start_time"]
        session_time = datetime.now(timezone.utc) - start_time
        work_data[user_id]["total_time"] += session_time
        clock_in_status[user_id] = False
        await log_action(interaction.user, "Clocked Out")
        await interaction.response.send_message(f"Clocked out. Session duration: {str(session_time).split('.')[0]}", ephemeral=True)

class TaskButton(discord.ui.Button):
    def __init__(self, label, style, row):
        super().__init__(label=label, style=style, row=row)

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if not clock_in_status.get(user_id, False):
            await interaction.response.send_message("You must be clocked in to perform this action.", ephemeral=True)
            return

        work_data[user_id][self.label] += 1
        await log_action(interaction.user, f"Completed: {self.label}")
        await interaction.response.send_message(f"{self.label} recorded!", ephemeral=True)

class CarPartButton(TaskButton):
    def __init__(self):
        super().__init__("Car Part", discord.ButtonStyle.primary, row=1)

class BikePartButton(TaskButton):
    def __init__(self):
        super().__init__("Bike Part", discord.ButtonStyle.primary, row=1)

class CarUpgradeButton(TaskButton):
    def __init__(self):
        super().__init__("Car Full Upgrade", discord.ButtonStyle.secondary, row=2)

class BikeUpgradeButton(TaskButton):
    def __init__(self):
        super().__init__("Bike Full Upgrade", discord.ButtonStyle.secondary, row=2)

class EngineUpgradeButton(TaskButton):
    def __init__(self):
        super().__init__("Engine Upgrade", discord.ButtonStyle.secondary, row=2)

class ResetLeaderboardButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Reset Leaderboard", style=discord.ButtonStyle.danger, row=3)

    async def callback(self, interaction: discord.Interaction):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("You do not have permission to reset.", ephemeral=True)
            return

        work_data.clear()
        clock_in_status.clear()
        strikes.clear()
        await log_action(interaction.user, "Reset the leaderboard")
        await interaction.response.send_message("Leaderboard has been reset.", ephemeral=True)

class RefreshLeaderboardButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Refresh Leaderboard", style=discord.ButtonStyle.primary, row=3)

    async def callback(self, interaction: discord.Interaction):
        await update_leaderboard()
        await interaction.response.send_message("Leaderboard refreshed.", ephemeral=True)

class AdminDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Force Clock Out", value="force_clockout"),
            discord.SelectOption(label="Remove Car Part", value="remove_car_part"),
            discord.SelectOption(label="Remove Bike Part", value="remove_bike_part"),
            discord.SelectOption(label="Remove Car Full Upgrade", value="remove_car_upgrade"),
            discord.SelectOption(label="Remove Bike Full Upgrade", value="remove_bike_upgrade"),
            discord.SelectOption(label="Remove Engine Upgrade", value="remove_engine_upgrade"),
            discord.SelectOption(label="Remove Time (3h)", value="remove_time"),
        ]
        super().__init__(placeholder="Admin Actions", options=options, row=4)

    async def callback(self, interaction: discord.Interaction):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("You are not allowed to use this.", ephemeral=True)
            return
        await interaction.response.send_message(f"Please use a command to specify the user for `{self.values[0]}` action.", ephemeral=True)

async def log_action(user, action):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"**{user.name}** - {action}")

async def update_leaderboard():
    leaderboard_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if leaderboard_channel:
        leaderboard_entries = []
        for user_id, data in work_data.items():
            member = leaderboard_channel.guild.get_member(int(user_id))
            if not member:
                continue
            total_earned = sum(data[task] * EARNINGS[task] for task in EARNINGS)
            status = ":green_circle:" if clock_in_status.get(user_id, False) else ":red_circle:"
            leaderboard_entries.append({
                "member": member.display_name,
                "status": status,
                "earned": total_earned,
                "time": str(data['total_time']).split('.')[0],
                **{k: data[k] for k in EARNINGS}
            })

        leaderboard_entries.sort(key=lambda x: x["earned"], reverse=True)

        embed = discord.Embed(title="📊 Work Leaderboard", color=discord.Color.gold())
        for entry in leaderboard_entries:
            embed.add_field(
                name=f"{entry['status']} **{entry['member']}**",
                value=(
                    f"**Time:** {entry['time']}\n"
                    f"Car Parts: {entry['Car Part']}\n"
                    f"Bike Parts: {entry['Bike Part']}\n"
                    f"Car Full Upgrades: {entry['Car Full Upgrade']}\n"
                    f"Bike Full Upgrades: {entry['Bike Full Upgrade']}\n"
                    f"Engine Upgrades: {entry['Engine Upgrade']}\n"
                    f"**Total Earned:** £{entry['earned']:,}"
                ),
                inline=False
            )

        await leaderboard_channel.purge()
        await leaderboard_channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    await panel_channel.purge()
    await panel_channel.send("**Work Tracker Panel**", view=WorkButtons())
    auto_clockout_check.start()

@tasks.loop(minutes=5)
async def auto_clockout_check():
    now = datetime.now(timezone.utc)
    for user_id, data in list(work_data.items()):
        if clock_in_status.get(user_id, False):
            start_time = data["start_time"]
            duration = now - start_time
            if duration >= timedelta(hours=3):
                member = bot.get_user(int(user_id))
                if not member:
                    continue
                try:
                    await member.send("⚠️ You've been clocked in for 3 hours. Please reply to stay clocked in.")
                    def check(m): return m.author.id == int(user_id)
                    await bot.wait_for('message', check=check, timeout=1800)
                    continue  # user responded
                except asyncio.TimeoutError:
                    data["total_time"] -= timedelta(hours=9)
                    clock_in_status[user_id] = False
                    strikes[user_id] = strikes.get(user_id, 0) + 1

                    log_channel = bot.get_channel(LOG_CHANNEL_ID)
                    if log_channel:
                        await log_channel.send(
                            f"⚠️ <@&{ADMIN_ROLE_ID}> Auto clocked out <@{user_id}> after 3h inactivity. "
                            f"-9h penalty. Strike {strikes[user_id]}/3."
                        )

                    try:
                        user = await bot.fetch_user(int(user_id))
                        if strikes[user_id] >= 3:
                            del work_data[user_id]
                            del strikes[user_id]
                            await user.send("🚨 You have received 3 strikes. Your data has been wiped and management has been notified.")
                        else:
                            await user.send(f"⚠️ You were auto-clocked out and penalized. You now have {strikes[user_id]} strike(s).")
                    except:
                        continue

bot.run(TOKEN)
