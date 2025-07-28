import discord
from discord.ext import tasks
from discord.ui import View, Button
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

clocked_in_users = {}
user_data = {}
strike_counts = {}
warning_tasks = {}

# CONFIG
PANEL_CHANNEL_ID = 1344409201123786758
LOG_CHANNEL_ID = 1390028891791298731
LEADERBOARD_CHANNEL_ID = 1364065995408281651
ADMIN_ROLE_ID = 1391785348262264925

leaderboard_message = None

class WorkButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in"))
        self.add_item(Button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out"))
        self.add_item(Button(label="Car Full Upgrade", style=discord.ButtonStyle.primary, custom_id="car_upgrade"))
        self.add_item(Button(label="Bike Full Upgrade", style=discord.ButtonStyle.primary, custom_id="bike_upgrade"))
        self.add_item(Button(label="Engine Upgrade", style=discord.ButtonStyle.primary, custom_id="engine_upgrade"))
        self.add_item(Button(label="Car Part", style=discord.ButtonStyle.secondary, custom_id="car_part"))
        self.add_item(Button(label="Bike Part", style=discord.ButtonStyle.secondary, custom_id="bike_part"))

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await tree.sync()
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    await channel.purge()
    await channel.send("**Work Tracker Panel**", view=WorkButtons())
    await update_leaderboard.start()

async def log_action(content):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    await log_channel.send(content)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    user_id = message.author.id
    if user_id in strike_counts:
        if user_id in clocked_in_users:
            now = datetime.utcnow()
            delta = (now - clocked_in_users[user_id]).total_seconds()
            user_data[user_id]["time_worked"] += delta
            clocked_in_users[user_id] = now
        strike_counts.pop(user_id)
        await message.channel.send("✅ Got your response. You’ll stay clocked in.")
        start_warning_timer(message.author)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    user = interaction.user
    user_id = user.id
    if interaction.data["component_type"] != 2:
        return

    now = datetime.utcnow()

    if user_id not in user_data:
        user_data[user_id] = {
            "car_upgrades": 0,
            "bike_upgrades": 0,
            "engine_upgrades": 0,
            "car_parts": 0,
            "bike_parts": 0,
            "time_worked": 0,
            "clocked_in": False
        }

    if interaction.data["custom_id"] == "clock_in":
        if user_data[user_id]["clocked_in"]:
            await interaction.response.send_message("⚠️ You are already clocked in.", ephemeral=True)
        else:
            clocked_in_users[user_id] = now
            user_data[user_id]["clocked_in"] = True
            await interaction.response.send_message("🟢 You are now clocked in.", ephemeral=True)
            await log_action(f"🟢 {user.mention} clocked in.")
            start_warning_timer(user)

   elif interaction.data["custom_id"] == "clock_out":
    if not user_data[user_id]["clocked_in"]:
        await interaction.response.send_message("⚠️ You are already clocked out.", ephemeral=True)
        return

    if user_id in clocked_in_users:
        delta = (now - clocked_in_users[user_id]).total_seconds()
        user_data[user_id]["time_worked"] += delta
        del clocked_in_users[user_id]

    user_data[user_id]["clocked_in"] = False
    await interaction.response.send_message("🔴 You are now clocked out.", ephemeral=True)
    await log_action(f"🔴 {user.mention} clocked out.")

    else:
        if not user_data[user_id]["clocked_in"]:
            await interaction.response.send_message("⛔ You must clock in first!", ephemeral=True)
            return

        task_map = {
            "car_upgrade": ("🚗 Car Full Upgrade", "car_upgrades", 500000),
            "bike_upgrade": ("🏍️ Bike Full Upgrade", "bike_upgrades", 250000),
            "engine_upgrade": ("🛠️ Engine Upgrade", "engine_upgrades", 250000),
            "car_part": ("🔧 Car Part", "car_parts", 20000),
            "bike_part": ("🔩 Bike Part", "bike_parts", 20000),
        }

        label, key, value = task_map[interaction.data["custom_id"]]
        user_data[user_id][key] += 1
        await interaction.response.send_message(f"{label} logged!", ephemeral=True)
        await log_action(f"{label} - {user.mention} completed task.")

    await update_leaderboard()

def start_warning_timer(user):
    user_id = user.id

    async def timer():
        await asyncio.sleep(5 * 60)  # 5 minutes
        if user_id not in clocked_in_users:
            return
        try:
            dm = await user.create_dm()
            await dm.send("⚠️ You’ve been clocked in for 15 minutes (test). Reply within 5 minutes or you’ll be auto-clocked out.")
            strike_counts[user_id] = 1
            await asyncio.sleep(1 * 60)  # 5 minutes
            if user_id in strike_counts:
                if user_id in clocked_in_users:
                    now = datetime.utcnow()
                    delta = (now - clocked_in_users[user_id]).total_seconds()
                    user_data[user_id]["time_worked"] += delta
                    del clocked_in_users[user_id]
                user_data[user_id]["clocked_in"] = False
                await dm.send("⛔ You were auto-clocked out (test strike 1).")
                await log_action(f"⛔ {user.mention} auto-clocked out after no reply. (test)")
        except:
            pass

    if user_id in warning_tasks:
        warning_tasks[user_id].cancel()

    warning_tasks[user_id] = asyncio.create_task(timer())

@tasks.loop(seconds=60)
async def update_leaderboard():
    global leaderboard_message
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)

    embed = discord.Embed(title="📊 Work Leaderboard", color=discord.Color.green())

    sorted_data = sorted(user_data.items(), key=lambda x: (
        x[1]["car_upgrades"] * 500000 +
        x[1]["bike_upgrades"] * 250000 +
        x[1]["engine_upgrades"] * 250000 +
        x[1]["car_parts"] * 20000 +
        x[1]["bike_parts"] * 20000
    ), reverse=True)

    total_bank = 0
    for user_id, data in sorted_data:
        member = await bot.fetch_user(user_id)
        if not member:
            continue

        total_time = data["time_worked"]
        if data["clocked_in"] and user_id in clocked_in_users:
            total_time += (datetime.utcnow() - clocked_in_users[user_id]).total_seconds()

        earnings = (
            data["car_upgrades"] * 500000 +
            data["bike_upgrades"] * 250000 +
            data["engine_upgrades"] * 250000 +
            data["car_parts"] * 20000 +
            data["bike_parts"] * 20000
        )
        total_bank += earnings

        clock_status = "🟢" if data["clocked_in"] else "🔴"

        embed.add_field(
            name=f"{clock_status} {member.name}",
            value=(
                f"🚗 Car Full Upgrades: {data['car_upgrades']}\n"
                f"🏍️ Bike Full Upgrades: {data['bike_upgrades']}\n"
                f"🛠️ Engine Upgrades: {data['engine_upgrades']}\n"
                f"🔧 Car Parts: {data['car_parts']}\n"
                f"🔩 Bike Parts: {data['bike_parts']}\n"
                f"⏱️ Time Worked: {int(total_time // 60)} mins\n"
                f"💰 Earnings: £{earnings:,}"
            ),
            inline=False
        )

    embed.set_footer(text=f"🏦 Total Bank: £{total_bank//2:,} (players keep 50%)")

    if leaderboard_message:
        try:
            await leaderboard_message.edit(embed=embed)
        except:
            leaderboard_message = await channel.send(embed=embed)
    else:
        leaderboard_message = await channel.send(embed=embed)

bot.run(os.getenv("DISCORD_TOKEN"))
