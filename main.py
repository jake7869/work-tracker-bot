
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
from datetime import datetime, timedelta

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
    buttons = [
        Button(label="Clock In", style=discord.ButtonStyle.green, custom_id="clock_in"),
        Button(label="Clock Out", style=discord.ButtonStyle.red, custom_id="clock_out"),
        Button(label="Car Full Upgrade", style=discord.ButtonStyle.blurple, custom_id="car_upgrade"),
        Button(label="Bike Full Upgrade", style=discord.ButtonStyle.blurple, custom_id="bike_upgrade"),
        Button(label="Engine Upgrade", style=discord.ButtonStyle.blurple, custom_id="engine_upgrade"),
        Button(label="Car Part", style=discord.ButtonStyle.gray, custom_id="car_part"),
        Button(label="Bike Part", style=discord.ButtonStyle.gray, custom_id="bike_part"),
    ]
    for button in buttons:
        view.add_item(button)

    await channel.send("**Work Tracker Panel**", view=view)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    user_id = interaction.user.id
    user = interaction.user
    data = user_data.setdefault(user_id, {
        "clocked_in": False, "start": None, "time": 0,
        "car": 0, "bike": 0, "engine": 0, "car_part": 0, "bike_part": 0
    })

    await interaction.response.defer()

    cid = interaction.data["custom_id"]
    now = datetime.utcnow()

    if cid == "clock_in":
        data["clocked_in"] = True
        data["start"] = now
        await log_action(f"🟢 Clock In - {user.mention}")
    elif cid == "clock_out":
        if data["clocked_in"]:
            elapsed = (now - data["start"]).total_seconds()
            data["time"] += int(elapsed)
            data["clocked_in"] = False
            data["start"] = None
            await log_action(f"🔴 Clock Out - {user.mention} ({int(elapsed // 60)} mins)")
    elif cid == "car_upgrade":
        if data["clocked_in"]:
            data["car"] += 1
            await log_action(f"🚗 Car Full Upgrade - {user.mention}")
        else:
            await interaction.followup.send("Clock in first!", ephemeral=True)
    elif cid == "bike_upgrade":
        if data["clocked_in"]:
            data["bike"] += 1
            await log_action(f"🛵 Bike Full Upgrade - {user.mention}")
        else:
            await interaction.followup.send("Clock in first!", ephemeral=True)
    elif cid == "engine_upgrade":
        if data["clocked_in"]:
            data["engine"] += 1
            await log_action(f"⚙️ Engine Upgrade - {user.mention}")
        else:
            await interaction.followup.send("Clock in first!", ephemeral=True)
    elif cid == "car_part":
        if data["clocked_in"]:
            data["car_part"] += 1
            await log_action(f"🧩 Car Part - {user.mention}")
        else:
            await interaction.followup.send("Clock in first!", ephemeral=True)
    elif cid == "bike_part":
        if data["clocked_in"]:
            data["bike_part"] += 1
            await log_action(f"🛠 Bike Part - {user.mention}")
        else:
            await interaction.followup.send("Clock in first!", ephemeral=True)

@tasks.loop(seconds=60)
async def check_clockout():
    now = datetime.utcnow()
    for user_id, data in list(user_data.items()):
        if data.get("clocked_in") and data.get("start"):
            elapsed = (now - data["start"]).total_seconds()
            if elapsed >= 3.5 * 3600:
                data["clocked_in"] = False
                data["start"] = None
                data["time"] = max(0, data["time"] - 32400)
                strikes[user_id] = strikes.get(user_id, 0) + 1
                user = await bot.fetch_user(user_id)
                await log_action(f"⚠️ Auto Clock-Out - {user.mention} (-9h, +1 strike)")
                if strikes[user_id] >= 3:
                    user_data.pop(user_id, None)
                    await log_action(f"❌ {user.mention}'s data wiped after 3 strikes")
                    strikes[user_id] = 0

@tasks.loop(seconds=120)
async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    await channel.purge()
    embed = discord.Embed(title="🏆 Work Leaderboard", color=0x00ff00)

    sorted_users = sorted(user_data.items(), key=lambda x: (
        x[1].get("car", 0)*850000 +
        x[1].get("bike", 0)*300000 +
        x[1].get("engine", 0)*500000 +
        x[1].get("car_part", 0)*50000 +
        x[1].get("bike_part", 0)*50000
    ), reverse=True)

    for user_id, data in sorted_users:
        total = (
            data["car"]*850000 +
            data["bike"]*300000 +
            data["engine"]*500000 +
            data["car_part"]*50000 +
            data["bike_part"]*50000
        )
        hours = str(timedelta(seconds=data["time"]))
        status = get_status_icon(user_id)
        name = f"{status} {get_username(channel.guild, user_id)}"
        embed.add_field(name=name, value=f"💰 £{total:,}
Time Worked: {hours}", inline=False)

    await channel.send(embed=embed)

async def log_action(message):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    await log_channel.send(message)

bot.run("YOUR_BOT_TOKEN")
