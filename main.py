import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Select
from discord import SelectOption
from datetime import datetime, timedelta
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Channel & Role IDs
PANEL_CHANNEL_ID = 1344409201123786758
LOG_CHANNEL_ID = 1390028891791298731
LEADERBOARD_CHANNEL_ID = 1364065995408281651
ADMIN_ROLE_ID = 1391785348262264925

# Data Storage
user_data = {}
clocked_in = {}
warning_sent = {}
strikes = {}
leaderboard_message = None
pending_confirmation = {}

# Task Pricing
TASKS = {
    "car_full": ("🚗", "Car Full Upgrade", 500000),
    "bike_full": ("🏍️", "Bike Full Upgrade", 250000),
    "engine": ("🛠️", "Engine Upgrade", 250000),
    "car_part": ("🔧", "Car Part", 20000),
    "bike_part": ("💪", "Bike Part", 20000),
}

class WorkButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clockin"))
        self.add_item(Button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clockout"))
        self.add_item(Button(label="Car Full Upgrade", style=discord.ButtonStyle.primary, custom_id="car_full"))
        self.add_item(Button(label="Bike Full Upgrade", style=discord.ButtonStyle.primary, custom_id="bike_full"))
        self.add_item(Button(label="Engine Upgrade", style=discord.ButtonStyle.primary, custom_id="engine"))
        self.add_item(Button(label="Car Part", style=discord.ButtonStyle.secondary, custom_id="car_part"))
        self.add_item(Button(label="Bike Part", style=discord.ButtonStyle.secondary, custom_id="bike_part"))

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await setup_panel()
    auto_clockout.start()
    await update_leaderboard()

async def setup_panel():
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    async for msg in channel.history(limit=10):
        if msg.author == bot.user:
            await msg.delete()
    await channel.send("**Work Tracker Panel**", view=WorkButtons())

@bot.event
async def on_interaction(interaction):
    if not interaction.type == discord.InteractionType.component:
        return
    uid = interaction.user.id
    if uid not in user_data:
        user_data[uid] = {"money": 0, "time": 0, "clocked_in": False, **{k: 0 for k in TASKS}}

    cid = interaction.data["custom_id"]
    if cid == "clockin":
        if uid in clocked_in:
            await interaction.response.send_message("🟡 Already clocked in!", ephemeral=True)
            return
        clocked_in[uid] = datetime.utcnow()
        user_data[uid]["clocked_in"] = True
        await interaction.response.send_message("🟢 You are now clocked in.", ephemeral=True)
        await log_action(f"🟢 {interaction.user.mention} clocked in.")
        await update_leaderboard()

    elif cid == "clockout":
        if uid not in clocked_in:
            await interaction.response.send_message("🔴 You are not clocked in.", ephemeral=True)
            return
        delta = (datetime.utcnow() - clocked_in.pop(uid)).total_seconds()
        user_data[uid]["time"] += int(delta)
        user_data[uid]["clocked_in"] = False
        await interaction.response.send_message("🔴 Clocked out.", ephemeral=True)
        await log_action(f"🔴 {interaction.user.mention} clocked out. Time added: {int(delta)}s")
        await update_leaderboard()

    elif cid in TASKS:
        if uid not in clocked_in:
            await interaction.response.send_message("❌ You must clock in first.", ephemeral=True)
            return
        emoji, name, pay = TASKS[cid]
        user_data[uid][cid] += 1
        user_data[uid]["money"] += pay
        await interaction.response.send_message(f"{emoji} {name} logged.", ephemeral=True)
        await log_action(f"{emoji} {interaction.user.mention} did {name} (+£{pay:,})")
        await update_leaderboard()

@tasks.loop(seconds=60)
async def auto_clockout():
    now = datetime.utcnow()
    for uid, start_time in list(clocked_in.items()):
        elapsed = (now - start_time).total_seconds()
        user = bot.get_user(uid)

        if uid in warning_sent:
            if elapsed >= 10800:  # 2.5 hours
                if uid not in pending_confirmation:
                    strikes[uid] = strikes.get(uid, 0) + 1
                    user_data[uid]["time"] = max(0, user_data[uid]["time"] - 21600)
                    try:
                        await user.send(f"⛔ You were auto-clocked out and received Strike {strikes[uid]}.")
                    except:
                        pass
                    await log_action(f"⛔ {user.mention} auto-clocked out. Strike {strikes[uid]}. <@&{ADMIN_ROLE_ID}>")
                    if strikes[uid] >= 3:
                        del user_data[uid]
                        strikes[uid] = 0
                        await log_action(f"❌ {user.mention} reached 3 strikes. Data wiped.")
                    clocked_in.pop(uid, None)
                    warning_sent.pop(uid, None)
                    await update_leaderboard()
        elif elapsed >= 7200:  # 2 hours
            try:
                await user.send("⚠️ You’ve been clocked in for 2 hours. Reply to stay clocked in or you’ll be removed in 30 minutes.")
                warning_sent[uid] = now
            except:
                pass

@bot.event
async def on_message(message):
    if message.guild is None and message.author.id in warning_sent:
        warning_sent.pop(message.author.id, None)
        await message.channel.send("✅ Got your response. You’ll stay clocked in.")
        await log_action(f"✅ {message.author.mention} replied to warning. No strike.")

async def update_leaderboard():
    global leaderboard_message
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)

    embed = discord.Embed(title="🏆 Work Leaderboard")
    bank_total = 0

    for uid, data in user_data.items():
        member = bot.get_user(uid)
        if not member:
            continue
        status = "🟢" if data["clocked_in"] else "🔴"
        money = data["money"]
        time = str(timedelta(seconds=data["time"]))
        bank_total += money // 2
        task_lines = [
            f"{TASKS[k][0]} {TASKS[k][1]}: {v}" for k, v in data.items() if k in TASKS
        ]
        embed.add_field(
            name=f"{status} {member.display_name} - £{money:,}",
            value=f"⏱️ Time Worked: {time}\n" + "\n".join(task_lines),
            inline=False
        )

    embed.add_field(name="🏦 Money in Bank", value=f"£{bank_total:,}", inline=False)

    if leaderboard_message:
        await leaderboard_message.edit(embed=embed)
    else:
        leaderboard_message = await channel.send(embed=embed)

async def log_action(content):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    await channel.send(content)

import os
bot.run(os.getenv("DISCORD_TOKEN"))
