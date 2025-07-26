
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Select
from datetime import datetime, timedelta
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

PANEL_CHANNEL_ID = 1344409201123786758
LOG_CHANNEL_ID = 1390028891791298731
LEADERBOARD_CHANNEL_ID = 1364065995408281651
ADMIN_ROLE_ID = 1391785348262264925

user_data = {}
strikes = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await send_panel()
    update_leaderboard.start()
    check_clockout.start()

def get_status_icon(user_id):
    if user_data.get(user_id, {}).get("clocked_in"):
        return "🟢"
    return "🔴"

def get_username(guild, user_id):
    member = guild.get_member(user_id)
    return member.name if member else f"<@{user_id}>"

async def send_panel():
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    await channel.purge()

    view = View(timeout=None)

    view.add_item(Button(label="Clock In", style=discord.ButtonStyle.green, custom_id="clock_in"))
    view.add_item(Button(label="Clock Out", style=discord.ButtonStyle.red, custom_id="clock_out"))
    view.add_item(Button(label="Car Full Upgrade", style=discord.ButtonStyle.blurple, custom_id="car_upgrade"))
    view.add_item(Button(label="Bike Full Upgrade", style=discord.ButtonStyle.blurple, custom_id="bike_upgrade"))
    view.add_item(Button(label="Engine Upgrade", style=discord.ButtonStyle.blurple, custom_id="engine_upgrade"))
    view.add_item(Button(label="Car Part", style=discord.ButtonStyle.gray, custom_id="car_part"))
    view.add_item(Button(label="Bike Part", style=discord.ButtonStyle.gray, custom_id="bike_part"))

    class AdminSelect(Select):
        def __init__(self):
            options = [
                discord.SelectOption(label="Force Clock Out", value="force_clockout"),
                discord.SelectOption(label="Remove Car Upgrade", value="remove_car"),
                discord.SelectOption(label="Remove Bike Upgrade", value="remove_bike"),
                discord.SelectOption(label="Remove Engine Upgrade", value="remove_engine"),
                discord.SelectOption(label="Remove Time", value="remove_time"),
                discord.SelectOption(label="Reset Leaderboard", value="reset_all")
            ]
            super().__init__(placeholder="Admin Options", options=options, custom_id="admin_dropdown")

        async def callback(self, interaction: discord.Interaction):
            if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
                await interaction.response.send_message("You don't have permission.", ephemeral=True)
                return

            if self.values[0] == "force_clockout":
                for user_id in user_data:
                    user_data[user_id]["clocked_in"] = False
                await log_action("⛔ Admin forced clock out for all users.")
            elif self.values[0] == "remove_car":
                for user_id in user_data:
                    user_data[user_id]["car"] = max(0, user_data[user_id].get("car", 0) - 1)
                await log_action("🗑 Admin removed 1 Car Full Upgrade from each user.")
            elif self.values[0] == "remove_bike":
                for user_id in user_data:
                    user_data[user_id]["bike"] = max(0, user_data[user_id].get("bike", 0) - 1)
                await log_action("🗑 Admin removed 1 Bike Full Upgrade from each user.")
            elif self.values[0] == "remove_engine":
                for user_id in user_data:
                    user_data[user_id]["engine"] = max(0, user_data[user_id].get("engine", 0) - 1)
                await log_action("🗑 Admin removed 1 Engine Upgrade from each user.")
            elif self.values[0] == "remove_time":
                for user_id in user_data:
                    user_data[user_id]["time"] = max(0, user_data[user_id].get("time", 0) - 3600)
                await log_action("⏱ Admin removed 1 hour from each user's time.")
            elif self.values[0] == "reset_all":
                user_data.clear()
                strikes.clear()
                await log_action("🔄 Admin reset the leaderboard and user data.")
            await interaction.response.defer()

    view.add_item(AdminSelect())
    await channel.send("**Work Tracker Panel**", view=view)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    user_id = interaction.user.id
    user = interaction.user
    data = user_data.setdefault(user_id, {"clocked_in": False, "start": None, "time": 0, "car": 0, "bike": 0, "engine": 0, "car_part": 0, "bike_part": 0})

    await interaction.response.defer()

    if interaction.data["custom_id"] == "clock_in":
        data["clocked_in"] = True
        data["start"] = datetime.utcnow()
        await log_action(f"🟢 Clock In - {user.mention}")
    elif interaction.data["custom_id"] == "clock_out":
        if data["clocked_in"]:
            elapsed = (datetime.utcnow() - data["start"]).total_seconds()
            data["time"] += int(elapsed)
            data["clocked_in"] = False
            data["start"] = None
            await log_action(f"🔴 Clock Out - {user.mention} ({int(elapsed // 60)} mins)")
    elif interaction.data["custom_id"] == "car_upgrade":
        if data["clocked_in"]:
            data["car"] += 1
            await log_action(f"🚗 Car Full Upgrade - {user.mention}")
        else:
            await interaction.followup.send("You must be clocked in.", ephemeral=True)
    elif interaction.data["custom_id"] == "bike_upgrade":
        if data["clocked_in"]:
            data["bike"] += 1
            await log_action(f"🛵 Bike Full Upgrade - {user.mention}")
        else:
            await interaction.followup.send("You must be clocked in.", ephemeral=True)
    elif interaction.data["custom_id"] == "engine_upgrade":
        if data["clocked_in"]:
            data["engine"] += 1
            await log_action(f"⚙️ Engine Upgrade - {user.mention}")
        else:
            await interaction.followup.send("You must be clocked in.", ephemeral=True)
    elif interaction.data["custom_id"] == "car_part":
        if data["clocked_in"]:
            data["car_part"] += 1
            await log_action(f"🧩 Car Part - {user.mention}")
        else:
            await interaction.followup.send("You must be clocked in.", ephemeral=True)
    elif interaction.data["custom_id"] == "bike_part":
        if data["clocked_in"]:
            data["bike_part"] += 1
            await log_action(f"🛠 Bike Part - {user.mention}")
        else:
            await interaction.followup.send("You must be clocked in.", ephemeral=True)

@tasks.loop(seconds=60)
async def check_clockout():
    for user_id, data in list(user_data.items()):
        if data.get("clocked_in") and data.get("start"):
            elapsed = (datetime.utcnow() - data["start"]).total_seconds()
            if elapsed >= 3 * 3600 + 1800:  # 3.5 hours passed
                user = await bot.fetch_user(user_id)
                data["clocked_in"] = False
                data["start"] = None
                data["time"] = max(0, data["time"] - 32400)  # -9 hours
                strikes[user_id] = strikes.get(user_id, 0) + 1
                await log_action(f"⚠️ Auto Clock-Out & Penalty: {user.mention} (-9h, +1 strike)")

                if strikes[user_id] >= 3:
                    user_data.pop(user_id, None)
                    strikes[user_id] = 0
                    await log_action(f"❌ {user.mention}'s data wiped after 3 strikes.")
    await update_leaderboard()

@tasks.loop(seconds=120)
async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    await channel.purge()

    embed = discord.Embed(title="🏆 Work Leaderboard", color=0x00ff00)

    for user_id, data in sorted(user_data.items(), key=lambda x: x[1].get("car", 0) + x[1].get("bike", 0) + x[1].get("engine", 0), reverse=True):
        total = (
            data.get("car", 0) * 850_000 +
            data.get("bike", 0) * 300_000 +
            data.get("engine", 0) * 500_000 +
            data.get("car_part", 0) * 50_000 +
            data.get("bike_part", 0) * 50_000
        )
        time = str(timedelta(seconds=data.get("time", 0)))
        status = get_status_icon(user_id)
        embed.add_field(name=f"{status} {get_username(channel.guild, user_id)}", value=f"💰 £{total:,}")
⏱️ {time}", inline=False)

    await channel.send(embed=embed)

async def log_action(message):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    await channel.send(message)

bot.run("YOUR_BOT_TOKEN")
