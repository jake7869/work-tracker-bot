import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
from datetime import datetime, timedelta, timezone
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

    view.add_item(Button(label="Clock In", style=discord.ButtonStyle.green, custom_id="clock_in"))
    view.add_item(Button(label="Clock Out", style=discord.ButtonStyle.red, custom_id="clock_out"))
    view.add_item(Button(label="Car Full Upgrade", style=discord.ButtonStyle.blurple, custom_id="car_upgrade"))
    view.add_item(Button(label="Bike Full Upgrade", style=discord.ButtonStyle.blurple, custom_id="bike_upgrade"))
    view.add_item(Button(label="Engine Upgrade", style=discord.ButtonStyle.blurple, custom_id="engine_upgrade"))
    view.add_item(Button(label="Car Part", style=discord.ButtonStyle.gray, custom_id="car_part"))
    view.add_item(Button(label="Bike Part", style=discord.ButtonStyle.gray, custom_id="bike_part"))

    class ResetButton(Button):
        def __init__(self):
            super().__init__(label="Reset Leaderboard", style=discord.ButtonStyle.danger, custom_id="reset_all")

        async def callback(self, interaction: discord.Interaction):
            if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
                await interaction.response.send_message("You don't have permission to use this.", ephemeral=True)
                return
            user_data.clear()
            strikes.clear()
            await update_leaderboard(force=True)
            await log_action(f"🔄 {interaction.user.mention} reset the leaderboard.")
            await interaction.response.send_message("Leaderboard has been reset.", ephemeral=True)

    view.add_item(ResetButton())
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
    now = datetime.now(timezone.utc)

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
        field_map = {
            "car_upgrade": "car",
            "bike_upgrade": "bike",
            "engine_upgrade": "engine",
            "car_part": "car_part",
            "bike_part": "bike_part"
        }
        label_map = {
            "car_upgrade": "🚗 Car Full Upgrade",
            "bike_upgrade": "🛵 Bike Full Upgrade",
            "engine_upgrade": "⚙️ Engine Upgrade",
            "car_part": "🧹 Car Part",
            "bike_part": "💪 Bike Part"
        }
        data[field_map[cid]] += 1
        await log_action(f"{label_map[cid]} - {user.mention}")

@tasks.loop(seconds=60)
async def check_clockout():
    now = datetime.now(timezone.utc)
    for user_id, data in list(user_data.items()):
        if data.get("clocked_in") and data.get("start"):
            elapsed = (now - data["start"]).total_seconds()

            if elapsed >= 3 * 3600 and user_id not in dm_warned:
                user = await bot.fetch_user(user_id)
                try:
                    await user.send("⏰ You've been clocked in for 3 hours. Please reply or clock out within 30 minutes, or you’ll be auto clocked out and penalized.")
                    dm_warned[user_id] = now
                except:
                    pass
            elif user_id in dm_warned:
                if (now - dm_warned[user_id]).total_seconds() >= 1800:
                    user = await bot.fetch_user(user_id)
                    data["clocked_in"] = False
                    data["start"] = None
                    data["time"] = max(0, data["time"] - 32400)
                    strikes[user_id] = strikes.get(user_id, 0) + 1
                    dm_warned.pop(user_id, None)
                    try:
                        await user.send("⚠️ You were auto clocked out for being AFK too long.\n\➖ 9 hours removed\n➕ 1 strike")
                    except:
                        pass
                    await log_action(f"🚨 Auto Clock-Out: {user.mention} (-9h, +1 strike) <@&{ADMIN_ROLE_ID}>")
                    if strikes[user_id] >= 3:
                        user_data.pop(user_id, None)
                        strikes[user_id] = 0
                        await log_action(f"❌ {user.mention}'s data wiped after 3 strikes <@&{ADMIN_ROLE_ID}>")

@tasks.loop(seconds=120)
async def update_leaderboard(force=False):
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not force:
        try:
            await channel.purge()
        except:
            pass

    embed = discord.Embed(title="🏆 Work Leaderboard", color=0x00ff00)
    total_money = 0

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
        total_money += total
        hours = str(timedelta(seconds=data["time"]))
        status = get_status_icon(user_id)
        name = f"{status} {get_username(channel.guild, user_id)}"
        value = (
            f"💰 £{total:,}\n"
            f"⏱ Time Worked: {hours}\n"
            f"🚗 {data['car']} | 🛵 {data['bike']} | ⚙️ {data['engine']}\n"
            f"🧹 {data['car_part']} | 💪 {data['bike_part']}"
        )
        embed.add_field(name=name, value=value, inline=False)

    embed.add_field(name="🏦 Money in Bank", value=f"£{int(total_money // 2):,}", inline=False)
    await channel.send(embed=embed)

async def log_action(message):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    await channel.send(message)

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
