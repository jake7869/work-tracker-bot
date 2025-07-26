import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.messages = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

PANEL_CHANNEL_ID = 1344409201123786758
LOG_CHANNEL_ID = 1390028891791298731
LEADERBOARD_CHANNEL_ID = 1364065995408281651
ADMIN_ROLE_ID = 1391785348262264925

user_data = {}
strikes = {}
dm_warned = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await send_panel()
    update_leaderboard.start()
    check_clockout.start()

def get_status_icon(user_id):
    return "🟢" if user_data.get(user_id, {}).get("clocked_in") else "🔴"

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
        dm_warned.pop(user_id, None)
        await log_action(f"🟢 Clock In - {user.mention}")
    elif cid == "clock_out":
        if data["clocked_in"]:
            elapsed = (now - data["start"]).total_seconds()
            data["time"] += int(elapsed)
            data["clocked_in"] = False
            data["start"] = None
            dm_warned.pop(user_id, None)
            await log_action(f"🔴 Clock Out - {user.mention} ({int(elapsed // 60)} mins)")
    elif cid in ["car_upgrade", "bike_upgrade", "engine_upgrade", "car_part", "bike_part"]:
        if not data["clocked_in"]:
            await interaction.followup.send("Clock in first!", ephemeral=True)
            return
        task_names = {
            "car_upgrade": "🚗 Car Full Upgrade",
            "bike_upgrade": "🛵 Bike Full Upgrade",
            "engine_upgrade": "⚙️ Engine Upgrade",
            "car_part": "🧩 Car Part",
            "bike_part": "🛠 Bike Part"
        }
        field_map = {
            "car_upgrade": "car",
            "bike_upgrade": "bike",
            "engine_upgrade": "engine",
            "car_part": "car_part",
            "bike_part": "bike_part"
        }
        data[field_map[cid]] += 1
        await log_action(f"{task_names[cid]} - {user.mention}")

@tasks.loop(seconds=60)
async def check_clockout():
    now = datetime.utcnow()
    for user_id, data in list(user_data.items()):
        if data.get("clocked_in") and data.get("start"):
            elapsed = (now - data["start"]).total_seconds()

            if elapsed >= 3 * 3600 and user_id not in dm_warned:
                user = await bot.fetch_user(user_id)
                try:
                    await user.send("⏰ You've been clocked in for 3 hours. Please reply to this message or manually clock out within 30 minutes, or you’ll be auto clocked out and penalized.")
                    dm_warned[user_id] = now
                except:
                    pass

            elif user_id in dm_warned:
                warning_time = dm_warned[user_id]
                if (now - warning_time).total_seconds() >= 1800:
                    user = await bot.fetch_user(user_id)
                    data["clocked_in"] = False
                    data["start"] = None
                    data["time"] = max(0, data["time"] - 32400)
                    dm_warned.pop(user_id, None)
                    strikes[user_id] = strikes.get(user_id, 0) + 1
                    try:
                        await user.send("⚠️ You were auto clocked out for being AFK too long.\n➖ 9 hours removed\n➕ 1 strike")
                    except:
                        pass
                    await log_action(f"🚨 Auto Clock-Out: {user.mention} (-9h, +1 strike) <@&{ADMIN_ROLE_ID}>")

                    if strikes[user_id] >= 3:
                        user_data.pop(user_id, None)
                        strikes[user_id] = 0
                        await log_action(f"❌ {user.mention}'s data wiped after 3 strikes <@&{ADMIN_ROLE_ID}>")

@tasks.loop(seconds=120)
async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    await channel.purge()
    embed = discord.Embed(title="🏆 Work Leaderboard", color=0x00ff00)

    sorted_users = sorted(user_data.items(), key=lambda x: (
        x[1]["car"] * 500000 +
        x[1]["bike"] * 250000 +
        x[1]["engine"] * 250000 +
        x[1]["car_part"] * 20000 +
        x[1]["bike_part"] * 20000
    ), reverse=True)

    for user_id, data in sorted_users:
        total = (
            data["car"] * 500000 +
            data["bike"] * 250000 +
            data["engine"] * 250000 +
            data["car_part"] * 20000 +
            data["bike_part"] * 20000
        )
        hours = str(timedelta(seconds=data["time"]))
        status = get_status_icon(user_id)
        name = f"{status} {get_username(channel.guild, user_id)}"
        value = f"💰 £{total:,}\nTime Worked: {hours}"
        embed.add_field(name=name, value=value, inline=False)

    await channel.send(embed=embed)

async def log_action(message):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    await log_channel.send(message)

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
