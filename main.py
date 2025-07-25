import discord
from discord.ext import commands, tasks
from discord.ui import View, Button, Select
from datetime import datetime, timedelta, timezone
import os
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))

work_data = {}
strikes = {}

# ----------------------------------------
# Logging
# ----------------------------------------
async def log_action(user, action):
    try:
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"**{user.name}** - {action}")
        else:
            print("❌ Log channel not found.")
    except Exception as e:
        print(f"❌ Failed to log: {e}")

# ----------------------------------------
# Utility
# ----------------------------------------
def calculate_total_earned(user_id):
    user = work_data.get(user_id, {})
    return (
        user.get("car_parts", 0) +
        user.get("bike_parts", 0) +
        user.get("car_upgrades", 0) * 17 +
        user.get("bike_upgrades", 0) * 6 +
        user.get("engine_upgrades", 0) * 10
    ) * 50000

def format_duration(seconds):
    return str(timedelta(seconds=int(seconds)))

# ----------------------------------------
# Autoclockout / Strike Loop
# ----------------------------------------
@tasks.loop(minutes=5)
async def clockout_checker():
    now = datetime.now(timezone.utc)
    for user_id, data in list(work_data.items()):
        if data.get("clocked_in") and "last_clock_in" in data:
            elapsed = (now - data["last_clock_in"]).total_seconds()
            if elapsed > 3 * 3600 and not data.get("warned"):  # 3 hours
                try:
                    user = await bot.fetch_user(user_id)
                    await user.send("⚠️ You’ve been clocked in for over 3 hours. Reply within 30 minutes to avoid penalty.")
                    data["warned"] = True
                    data["warned_time"] = now
                except:
                    pass
            elif data.get("warned") and "warned_time" in data:
                warned_elapsed = (now - data["warned_time"]).total_seconds()
                if warned_elapsed > 1800:  # 30 min passed, no reply
                    work_data[user_id]["clocked_in"] = False
                    work_data[user_id]["warned"] = False
                    work_data[user_id]["total_time"] = max(0, data.get("total_time", 0) - 9 * 3600)
                    strikes[user_id] = strikes.get(user_id, 0) + 1
                    try:
                        user = await bot.fetch_user(user_id)
                        await user.send(f"⛔ You’ve been auto-clocked out and lost 9 hours. Strike {strikes[user_id]}/3.")
                        await log_action(user, f"Auto clock-out. 9h removed. Strike {strikes[user_id]}/3. <@&{ADMIN_ROLE_ID}>")
                        if strikes[user_id] >= 3:
                            work_data.pop(user_id, None)
                            await user.send("❌ You’ve reached 3 strikes. Your data has been wiped. Management has been informed.")
                            await log_action(user, f"Data wiped after 3 strikes. <@&{ADMIN_ROLE_ID}>")
                    except:
                        pass

# ----------------------------------------
# Buttons
# ----------------------------------------
class WorkButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in"))
        self.add_item(Button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out"))
        self.add_item(Button(label="Car Part", style=discord.ButtonStyle.primary, custom_id="car_part"))
        self.add_item(Button(label="Bike Part", style=discord.ButtonStyle.primary, custom_id="bike_part"))
        self.add_item(Button(label="Car Full Upgrade", style=discord.ButtonStyle.secondary, custom_id="car_upgrade"))
        self.add_item(Button(label="Bike Full Upgrade", style=discord.ButtonStyle.secondary, custom_id="bike_upgrade"))
        self.add_item(Button(label="Engine Upgrade", style=discord.ButtonStyle.secondary, custom_id="engine_upgrade"))
        self.add_item(Button(label="Reset Leaderboard", style=discord.ButtonStyle.danger, custom_id="reset"))
        self.add_item(Button(label="Refresh Leaderboard", style=discord.ButtonStyle.primary, custom_id="refresh"))
        self.add_item(AdminDropdown())

class AdminDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Force Clock Out", value="force_clock_out"),
            discord.SelectOption(label="Remove Car Upgrade", value="remove_car_upgrade"),
            discord.SelectOption(label="Remove Bike Upgrade", value="remove_bike_upgrade"),
            discord.SelectOption(label="Remove Engine Upgrade", value="remove_engine_upgrade"),
            discord.SelectOption(label="Remove Car Part", value="remove_car_part"),
            discord.SelectOption(label="Remove Bike Part", value="remove_bike_part"),
            discord.SelectOption(label="Remove Time", value="remove_time"),
        ]
        super().__init__(placeholder="Admin Actions", options=options, custom_id="admin_dropdown")

    async def callback(self, interaction: discord.Interaction):
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("You don't have permission to use this.", ephemeral=True)
            return
        await interaction.response.send_message(f"Selected: {self.values[0]} (not implemented)", ephemeral=True)

# ----------------------------------------
# Interaction Handler
# ----------------------------------------
@bot.event
async def on_interaction(interaction):
    if not interaction.type == discord.InteractionType.component:
        return
    user = interaction.user
    user_id = user.id
    if user_id not in work_data:
        work_data[user_id] = {"clocked_in": False, "total_time": 0, "car_parts": 0, "bike_parts": 0,
                              "car_upgrades": 0, "bike_upgrades": 0, "engine_upgrades": 0}
    data = work_data[user_id]

    now = datetime.now(timezone.utc)

    match interaction.data["custom_id"]:
        case "clock_in":
            if data["clocked_in"]:
                await interaction.response.send_message("You're already clocked in.", ephemeral=True)
                return
            data["clocked_in"] = True
            data["last_clock_in"] = now
            await interaction.response.send_message("✅ Clocked in.", ephemeral=True)
            await log_action(user, "Clocked In")
        case "clock_out":
            if not data["clocked_in"]:
                await interaction.response.send_message("You're not clocked in.", ephemeral=True)
                return
            session = (now - data["last_clock_in"]).total_seconds()
            data["total_time"] += session
            data["clocked_in"] = False
            await interaction.response.send_message("👋 Clocked out.", ephemeral=True)
            await log_action(user, f"Clocked Out – Time added: {format_duration(session)}")
        case "car_part":
            if not data["clocked_in"]:
                await interaction.response.send_message("Clock in first.", ephemeral=True)
                return
            data["car_parts"] += 1
            await interaction.response.send_message("Added Car Part.", ephemeral=True)
            await log_action(user, "Completed: Car Part")
        case "bike_part":
            if not data["clocked_in"]:
                await interaction.response.send_message("Clock in first.", ephemeral=True)
                return
            data["bike_parts"] += 1
            await interaction.response.send_message("Added Bike Part.", ephemeral=True)
            await log_action(user, "Completed: Bike Part")
        case "car_upgrade":
            if not data["clocked_in"]:
                await interaction.response.send_message("Clock in first.", ephemeral=True)
                return
            data["car_upgrades"] += 1
            await interaction.response.send_message("Added Car Full Upgrade.", ephemeral=True)
            await log_action(user, "Completed: Car Full Upgrade")
        case "bike_upgrade":
            if not data["clocked_in"]:
                await interaction.response.send_message("Clock in first.", ephemeral=True)
                return
            data["bike_upgrades"] += 1
            await interaction.response.send_message("Added Bike Full Upgrade.", ephemeral=True)
            await log_action(user, "Completed: Bike Full Upgrade")
        case "engine_upgrade":
            if not data["clocked_in"]:
                await interaction.response.send_message("Clock in first.", ephemeral=True)
                return
            data["engine_upgrades"] += 1
            await interaction.response.send_message("Added Engine Upgrade.", ephemeral=True)
            await log_action(user, "Completed: Engine Upgrade")
        case "reset":
            if ADMIN_ROLE_ID not in [r.id for r in user.roles]:
                await interaction.response.send_message("You don't have permission.", ephemeral=True)
                return
            work_data.clear()
            await interaction.response.send_message("Leaderboard reset.", ephemeral=True)
            await log_action(user, "Reset leaderboard")
        case "refresh":
            await send_leaderboard()
            await interaction.response.send_message("Refreshed.", ephemeral=True)

# ----------------------------------------
# Leaderboard
# ----------------------------------------
async def send_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        print("❌ Leaderboard channel not found.")
        return
    sorted_data = sorted(work_data.items(), key=lambda x: calculate_total_earned(x[0]), reverse=True)
    embeds = []
    for user_id, data in sorted_data:
        try:
            member = await bot.fetch_user(user_id)
            emoji = ":green_circle:" if data.get("clocked_in") else ":red_circle:"
            earned = calculate_total_earned(user_id)
            embed = discord.Embed(title="📊 Work Leaderboard", color=discord.Color.gold())
            embed.add_field(name=f"{emoji} {member.name}", value=(
                f"**Time:** {format_duration(data.get('total_time', 0))}\n"
                f"**Car Parts:** {data['car_parts']}\n"
                f"**Bike Parts:** {data['bike_parts']}\n"
                f"**Car Full Upgrades:** {data['car_upgrades']}\n"
                f"**Bike Full Upgrades:** {data['bike_upgrades']}\n"
                f"**Engine Upgrades:** {data['engine_upgrades']}\n"
                f"**Total Earned:** £{earned:,}"
            ), inline=False)
            embeds.append(embed)
        except Exception as e:
            print(f"❌ Failed to fetch leaderboard user: {e}")

    await channel.purge(limit=10)
    for e in embeds:
        await channel.send(embed=e)

# ----------------------------------------
# Ready
# ----------------------------------------
@bot.event
async def on_ready():
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        await panel_channel.send("**Work Tracker Panel**", view=WorkButtons())
    await send_leaderboard()
    clockout_checker.start()
    print(f"✅ Logged in as {bot.user}")

bot.run(TOKEN)
