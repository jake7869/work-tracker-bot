import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import asyncio

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

PANEL_CHANNEL_ID = 1344409201123786758
LOG_CHANNEL_ID = 1390028891791298731
LEADERBOARD_CHANNEL_ID = 1364065995408281651
ADMIN_ROLE_ID = 1391785348262264925

clocked_in_users = {}
user_data = {}
strike_counts = {}
leaderboard_message = None

TASK_VALUES = {
    'car_full': 500000,
    'bike_full': 250000,
    'engine': 250000,
    'car_part': 20000,
    'bike_part': 20000
}

class WorkButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(WorkButton(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in"))
        self.add_item(WorkButton(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out"))
        self.add_item(WorkButton(label="Car Full Upgrade", style=discord.ButtonStyle.primary, custom_id="car_full"))
        self.add_item(WorkButton(label="Bike Full Upgrade", style=discord.ButtonStyle.primary, custom_id="bike_full"))
        self.add_item(WorkButton(label="Engine Upgrade", style=discord.ButtonStyle.primary, custom_id="engine"))
        self.add_item(WorkButton(label="Car Part", style=discord.ButtonStyle.secondary, custom_id="car_part"))
        self.add_item(WorkButton(label="Bike Part", style=discord.ButtonStyle.secondary, custom_id="bike_part"))

class WorkButton(discord.ui.Button):
    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        user_id = user.id
        now = datetime.utcnow()

        if self.custom_id == "clock_in":
            if user_id in clocked_in_users:
                await interaction.response.send_message("🟡 You're already clocked in.", ephemeral=True)
                return
            clocked_in_users[user_id] = now
            user_data.setdefault(user_id, {
                "username": user.name,
                "clocked_in": True,
                "time_worked": 0,
                "car_full": 0,
                "bike_full": 0,
                "engine": 0,
                "car_part": 0,
                "bike_part": 0
            })
            user_data[user_id]["clocked_in"] = True
            await interaction.response.send_message("🟢 You are now clocked in.", ephemeral=True)
            await log_action(f"✅ {user.mention} clocked in.")

        elif self.custom_id == "clock_out":
            if user_id not in clocked_in_users:
                await interaction.response.send_message("🔴 You're not clocked in.", ephemeral=True)
                return
            delta = (now - clocked_in_users.pop(user_id)).total_seconds()
            user_data[user_id]["time_worked"] += delta
            user_data[user_id]["clocked_in"] = False
            await interaction.response.send_message("🔴 You are now clocked out.", ephemeral=True)
            await log_action(f"🚪 {user.mention} clocked out. Time worked: {int(delta // 60)} minutes.")

        else:
            if user_id not in clocked_in_users:
                await interaction.response.send_message("⚠️ You must be clocked in to do this task.", ephemeral=True)
                return
            user_data.setdefault(user_id, {
                "username": user.name,
                "clocked_in": True,
                "time_worked": 0,
                "car_full": 0,
                "bike_full": 0,
                "engine": 0,
                "car_part": 0,
                "bike_part": 0
            })
            user_data[user_id][self.custom_id] += 1
            await interaction.response.send_message(f"✅ Logged task: {self.label}", ephemeral=True)
            await log_action(f"🔧 {user.mention} completed **{self.label}**.")
        await update_leaderboard()

async def log_action(message):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(message)

async def update_leaderboard():
    global leaderboard_message
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return

    sorted_users = sorted(user_data.items(), key=lambda x: total_earnings(x[1]), reverse=True)

    description = ""
    for user_id, data in sorted_users:
        status = "🟢" if data.get("clocked_in") else "🔴"
        name = data.get("username", f"<@{user_id}>")
        earnings = total_earnings(data)
        description += (
            f"{status} **{name}**\n"
            f"> 🚗 Car Full Upgrades: {data['car_full']}\n"
            f"> 🏍️ Bike Full Upgrades: {data['bike_full']}\n"
            f"> ⚙️ Engine Upgrades: {data['engine']}\n"
            f"> 🧩 Car Parts: {data['car_part']}\n"
            f"> 🔩 Bike Parts: {data['bike_part']}\n"
            f"> 🕒 Time Worked: {int(data['time_worked'] // 60)} mins\n"
            f"> 💸 Total Earnings: £{earnings:,}\n\n"
        )

    total_bank = sum(total_earnings(data) for _, data in sorted_users) // 2
    embed = discord.Embed(title="📊 Work Leaderboard", description=description or "No data yet.", color=0x00ff00)
    embed.set_footer(text=f"🏦 Bank Total: £{total_bank:,}")

    if leaderboard_message:
        try:
            await leaderboard_message.edit(embed=embed)
        except:
            leaderboard_message = await channel.send(embed=embed)
    else:
        leaderboard_message = await channel.send(embed=embed)

def total_earnings(data):
    return sum(data[task] * TASK_VALUES[task] for task in TASK_VALUES)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.add_view(WorkButtons())
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if channel:
        await channel.send("**__Work Tracker Panel__**", view=WorkButtons())
    auto_clockout_check.start()
    await update_leaderboard()

@tasks.loop(minutes=1)
async def auto_clockout_check():
    now = datetime.utcnow()
    to_warn = []
    to_clockout = []

    for user_id, start_time in clocked_in_users.items():
        elapsed = now - start_time
        if elapsed >= timedelta(hours=2, minutes=30):
            to_clockout.append(user_id)
        elif elapsed >= timedelta(hours=2) and user_id not in strike_counts:
            to_warn.append(user_id)

    for user_id in to_warn:
        user = await bot.fetch_user(user_id)
        try:
            await user.send("⚠️ You’ve been clocked in for 2 hours. Reply to stay clocked in or you’ll be removed in 30 minutes.")
            strike_counts[user_id] = now
        except:
            pass

    for user_id in to_clockout:
        if user_id not in strike_counts:
            continue
        if (now - strike_counts[user_id]) < timedelta(minutes=30):
            continue

        user = await bot.fetch_user(user_id)
        user_data[user_id]["clocked_in"] = False
        if user_id in clocked_in_users:
            delta = (now - clocked_in_users.pop(user_id)).total_seconds()
            user_data[user_id]["time_worked"] += delta

        count = strike_counts.get(user_id, 0)
        count += 1
        strike_counts[user_id] = count

        try:
            await user.send(f"⛔ You were auto-clocked out and received Strike {count}.")
        except:
            pass

        await log_action(f"⚠️ <@{user_id}> auto-clocked out and given Strike {count} <@&{ADMIN_ROLE_ID}>")

        if count >= 3:
            user_data.pop(user_id, None)
            strike_counts.pop(user_id, None)
            await log_action(f"❌ <@{user_id}> data wiped after 3 strikes <@&{ADMIN_ROLE_ID}>")

    await update_leaderboard()

@bot.event
async def on_message(message):
    if message.guild is None and not message.author.bot:
        user_id = message.author.id
        if user_id in strike_counts:
            strike_counts.pop(user_id)
            clocked_in_users[user_id] = datetime.utcnow()  # Reset their clock
            await message.channel.send("✅ Got your response. You’ll stay clocked in.")
    await bot.process_commands(message)
    
import os
bot.run(os.getenv("DISCORD_TOKEN"))
