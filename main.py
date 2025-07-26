import discord
from discord.ext import commands, tasks
import asyncio
import datetime

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ====== CONFIG ======
PANEL_CHANNEL_ID = 1344409201123786758
LEADERBOARD_CHANNEL_ID = 1364065995408281651
LOG_CHANNEL_ID = 1390028891791298731
ADMIN_ROLE_ID = 1391785348262264925
AUTO_CLOCKOUT_MINUTES = 120  # 2 hours

# ====== DATA ======
data = {}
clocked_in_users = {}
leaderboard_message = None

PRICES = {
    'car_part': 20000,
    'bike_part': 20000,
    'engine_upgrade': 250000,
    'car_upgrade': 500000,
    'bike_upgrade': 250000,
}

TASK_LABELS = {
    'car_upgrade': "Car Full Upgrades",
    'bike_upgrade': "Bike Full Upgrades",
    'engine_upgrade': "Engine Upgrades",
    'car_part': "Car Parts",
    'bike_part': "Bike Parts",
}

TASK_ICONS = {
    'car_upgrade': "🚗",
    'bike_upgrade': "🏍️",
    'engine_upgrade': "⚙️",
    'car_part': "✈️",
    'bike_part': "💪",
}

# ====== UTILS ======
def get_username(guild, user_id):
    member = guild.get_member(user_id)
    return member.display_name if member else f"<@{user_id}>"

def format_timedelta(seconds):
    return str(datetime.timedelta(seconds=int(seconds)))

# ====== VIEW ======
class WorkButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in clocked_in_users:
            await interaction.response.send_message("⚠️ You're already clocked in!", ephemeral=True)
            return
        clocked_in_users[user_id] = datetime.datetime.utcnow()
        data.setdefault(user_id, {task: 0 for task in TASK_LABELS})
        data[user_id].setdefault("time", 0)
        data[user_id].setdefault("total", 0)
        await interaction.response.send_message("📊 You are now clocked in.", ephemeral=True)
        await update_leaderboard(interaction.guild)

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id not in clocked_in_users:
            await interaction.response.send_message("❌ You are not clocked in.", ephemeral=True)
            return
        delta = (datetime.datetime.utcnow() - clocked_in_users[user_id]).total_seconds()
        data[user_id]["time"] += delta
        del clocked_in_users[user_id]
        await interaction.response.send_message("⏹️ You are now clocked out.", ephemeral=True)
        await update_leaderboard(interaction.guild)

    @discord.ui.button(label="Car Full Upgrade", style=discord.ButtonStyle.primary, custom_id="car_upgrade")
    async def car_upgrade(self, interaction, button):
        await log_task(interaction, "car_upgrade")

    @discord.ui.button(label="Bike Full Upgrade", style=discord.ButtonStyle.primary, custom_id="bike_upgrade")
    async def bike_upgrade(self, interaction, button):
        await log_task(interaction, "bike_upgrade")

    @discord.ui.button(label="Engine Upgrade", style=discord.ButtonStyle.primary, custom_id="engine_upgrade")
    async def engine_upgrade(self, interaction, button):
        await log_task(interaction, "engine_upgrade")

    @discord.ui.button(label="Car Part", style=discord.ButtonStyle.secondary, custom_id="car_part")
    async def car_part(self, interaction, button):
        await log_task(interaction, "car_part")

    @discord.ui.button(label="Bike Part", style=discord.ButtonStyle.secondary, custom_id="bike_part")
    async def bike_part(self, interaction, button):
        await log_task(interaction, "bike_part")

# ====== TASK LOGGING ======
async def log_task(interaction, task):
    user_id = interaction.user.id
    if user_id not in clocked_in_users:
        await interaction.response.send_message("Please clock in before doing tasks!", ephemeral=True)
        return
    data.setdefault(user_id, {task: 0 for task in TASK_LABELS})
    data[user_id][task] += 1
    data[user_id]["total"] += PRICES[task]
    await interaction.response.send_message(f"{TASK_ICONS[task]} {TASK_LABELS[task]} logged. £{PRICES[task]:,} earned.", ephemeral=True)
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    await log_channel.send(f"{interaction.user.mention} completed: **{TASK_LABELS[task]}** - Earned £{PRICES[task]:,}")
    await update_leaderboard(interaction.guild)

# ====== LEADERBOARD ======
async def update_leaderboard(guild):
    global leaderboard_message
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    embed = discord.Embed(title="🏆 Work Leaderboard", color=discord.Color.green())
    total_bank = 0
    for user_id, stats in data.items():
        name = get_username(guild, user_id)
        earnings = stats["total"]
        time_worked = stats["time"]
        if user_id in clocked_in_users:
            delta = (datetime.datetime.utcnow() - clocked_in_users[user_id]).total_seconds()
            time_worked += delta
        status = "🟢" if user_id in clocked_in_users else "🔴"
        desc = f"{status} {name}\n💰 £{earnings:,}\n⏱️ Time Worked: {format_timedelta(time_worked)}"
        for task, label in TASK_LABELS.items():
            icon = TASK_ICONS[task]
            desc += f"\n{icon} {label}: {stats.get(task, 0)}"
        desc += f"\n\n\U0001f3e6 **Money in Bank**\n£{earnings // 2:,}"
        embed.add_field(name="\u200b", value=desc, inline=False)
        total_bank += earnings
    embed.set_footer(text=f"\U0001f3e6 Total Money in Bank: £{total_bank // 2:,}")
    if leaderboard_message:
        await leaderboard_message.edit(embed=embed)
    else:
        leaderboard_message = await channel.send(embed=embed)

# ====== AUTO CLOCK-OUT CHECK ======
@tasks.loop(minutes=30)
async def auto_clockout():
    now = datetime.datetime.utcnow()
    for user_id, clocked_time in list(clocked_in_users.items()):
        elapsed = (now - clocked_time).total_seconds()
        if elapsed > AUTO_CLOCKOUT_MINUTES * 60:
            member = await bot.fetch_user(user_id)
            try:
                await member.send("You have been auto-clocked out due to inactivity.")
            except:
                pass
            data[user_id]["time"] += elapsed
            del clocked_in_users[user_id]
            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            await log_channel.send(f"⚠️ {member.mention} auto-clocked out after {AUTO_CLOCKOUT_MINUTES} minutes.")

# ====== EVENTS ======
@bot.event
async def on_ready():
    global leaderboard_message
    print(f"Logged in as {bot.user}")
    bot.add_view(WorkButtons())
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    await panel_channel.purge(limit=5)
    await panel_channel.send("**Work Tracker Panel**", view=WorkButtons())
    leaderboard_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    async for msg in leaderboard_channel.history(limit=10):
        if msg.author == bot.user:
            leaderboard_message = msg
            break
    await update_leaderboard(panel_channel.guild)
    auto_clockout.start()

import os
bot.run(os.getenv("DISCORD_TOKEN"))
