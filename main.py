import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Select
import asyncio
from datetime import datetime, timedelta

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# CHANNELS
PANEL_CHANNEL = 1344409201123786758
LOG_CHANNEL = 1390028891791298731
LEADERBOARD_CHANNEL = 1364065995408281651
ADMIN_ROLE_ID = 1391785348262264925

# Global state
clocked_in_users = {}
user_data = {}
leaderboard_message_id = None
warning_sent = {}

TASKS = {
    "car": {"label": "Car Full Upgrade", "emoji": "🚗", "amount": 500_000},
    "bike": {"label": "Bike Full Upgrade", "emoji": "🏍️", "amount": 250_000},
    "engine": {"label": "Engine Upgrade", "emoji": "⚙️", "amount": 250_000},
    "carpart": {"label": "Car Part", "emoji": "🛠️", "amount": 20_000},
    "bikepart": {"label": "Bike Part", "emoji": "💪", "amount": 20_000},
}

def get_user_display_name(user):
    return user.global_name or user.name

def format_time(seconds):
    return str(timedelta(seconds=int(seconds)))

def get_status_emoji(user_id):
    return "🟢" if user_id in clocked_in_users else "🔴"

def calculate_total_bank():
    return sum(u["money"] for u in user_data.values()) // 2

def get_leaderboard_embed():
    embed = discord.Embed(title="🏆 Work Leaderboard", color=discord.Color.orange())
    for user_id, data in user_data.items():
        status = get_status_emoji(user_id)
        name = data.get("name", "Unknown")
        money = data.get("money", 0)
        time_worked = data.get("time", 0)
        task_lines = "\n".join(
            f"{TASKS[key]['emoji']} {TASKS[key]['label']}: {data.get(key, 0)}"
            for key in TASKS
        )
        embed.add_field(
            name=f"{status} {name}",
            value=f"💰 £{money:,}\n⏱️ Time Worked: {format_time(time_worked)}\n{task_lines}",
            inline=False,
        )
    embed.add_field(
        name="🏛️ Money in Bank",
        value=f"£{calculate_total_bank():,}",
        inline=False,
    )
    return embed

async def update_leaderboard():
    global leaderboard_message_id
    channel = bot.get_channel(LEADERBOARD_CHANNEL)
    if leaderboard_message_id:
        try:
            msg = await channel.fetch_message(leaderboard_message_id)
            await msg.edit(embed=get_leaderboard_embed())
        except:
            msg = await channel.send(embed=get_leaderboard_embed())
            leaderboard_message_id = msg.id
    else:
        msg = await channel.send(embed=get_leaderboard_embed())
        leaderboard_message_id = msg.id

async def log_action(message):
    channel = bot.get_channel(LOG_CHANNEL)
    await channel.send(message)

async def warn_user(user):
    try:
        await user.send("⚠️ You’ve been clocked in for 2 hours. Please reply to stay clocked in or you will be auto-clocked out in 30 minutes.")
        warning_sent[user.id] = datetime.utcnow()
    except:
        pass

async def strike_user(user):
    uid = user.id
    data = user_data.get(uid, {})
    data["strikes"] = data.get("strikes", 0) + 1
    data["time"] = max(0, data.get("time", 0) - 6 * 3600)
    user_data[uid] = data

    await user.send(f"⛔ You were auto clocked out for being inactive. Strike {data['strikes']} applied. 6h removed.")
    await log_action(f"⚠️ {user.mention} was auto-clocked out. Strike {data['strikes']} given. <@&{ADMIN_ROLE_ID}>")

    if data["strikes"] >= 3:
        user_data.pop(uid)
        await log_action(f"❌ {user.mention} reached 3 strikes and was removed from leaderboard.")
    await update_leaderboard()

@tasks.loop(minutes=1)
async def check_clockouts():
    now = datetime.utcnow()
    to_remove = []
    for uid, start in clocked_in_users.items():
        user = bot.get_user(uid)
        if uid in warning_sent:
            if (now - warning_sent[uid]).total_seconds() > 1800:
                to_remove.append(uid)
                await strike_user(user)
                continue
        elif (now - start).total_seconds() > 7200:
            await warn_user(user)

    for uid in to_remove:
        clocked_in_users.pop(uid, None)
        warning_sent.pop(uid, None)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.wait_until_ready()
    await update_leaderboard()
    check_clockouts.start()

class WorkButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        for key, task in TASKS.items():
            self.add_item(Button(label=task["label"], emoji=task["emoji"], custom_id=key, style=discord.ButtonStyle.primary))
        self.add_item(Button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clockin"))
        self.add_item(Button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clockout"))
        self.add_item(Button(label="Reset Leaderboard", style=discord.ButtonStyle.secondary, custom_id="reset"))

@bot.event
async def on_interaction(interaction):
    if not interaction.type == discord.InteractionType.component:
        return
    uid = interaction.user.id
    name = get_user_display_name(interaction.user)
    now = datetime.utcnow()

    if interaction.data["custom_id"] == "clockin":
        if uid in clocked_in_users:
            await interaction.response.send_message("❌ You are already clocked in.", ephemeral=True)
            return
        clocked_in_users[uid] = now
        if uid not in user_data:
            user_data[uid] = {"name": name, "money": 0, "time": 0, "strikes": 0, **{k: 0 for k in TASKS}}
        await interaction.response.send_message("🟢 You are now clocked in.", ephemeral=True)
        await update_leaderboard()
        await log_action(f"🟢 {interaction.user.mention} clocked in.")

    elif interaction.data["custom_id"] == "clockout":
        if uid not in clocked_in_users:
            await interaction.response.send_message("❌ You are not clocked in.", ephemeral=True)
            return
        delta = (now - clocked_in_users.pop(uid)).total_seconds()
        user_data[uid]["time"] += delta
        warning_sent.pop(uid, None)
        await interaction.response.send_message("🔴 You are now clocked out.", ephemeral=True)
        await update_leaderboard()
        await log_action(f"🔴 {interaction.user.mention} clocked out. Time added: {format_time(delta)}")

    elif interaction.data["custom_id"] == "reset":
        if ADMIN_ROLE_ID in [role.id for role in interaction.user.roles]:
            user_data.clear()
            clocked_in_users.clear()
            warning_sent.clear()
            await update_leaderboard()
            await interaction.response.send_message("✅ Leaderboard reset.", ephemeral=True)
            await log_action(f"♻️ {interaction.user.mention} reset the leaderboard.")
        else:
            await interaction.response.send_message("❌ You are not authorized.", ephemeral=True)

    elif interaction.data["custom_id"] in TASKS:
        if uid not in clocked_in_users:
            await interaction.response.send_message("❌ You must clock in first.", ephemeral=True)
            return
        task_key = interaction.data["custom_id"]
        user_data[uid][task_key] += 1
        user_data[uid]["money"] += TASKS[task_key]["amount"]
        await interaction.response.send_message(f"✅ {TASKS[task_key]['label']} logged.", ephemeral=True)
        await update_leaderboard()
        await log_action(f"{interaction.user.mention} completed {TASKS[task_key]['label']}.")

@bot.command()
@commands.has_role(ADMIN_ROLE_ID)
async def panel(ctx):
    channel = bot.get_channel(PANEL_CHANNEL)
    await channel.send("**Work Panel**", view=WorkButtons())

import os
bot.run(os.getenv("DISCORD_TOKEN"))
