import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import datetime, timedelta, timezone
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- CONFIG ---
WORK_CHANNEL_ID = 1344409201123786758
LOG_CHANNEL_ID = 1364066063691546654
LEADERBOARD_CHANNEL_ID = 1364065995408281651
BACKUP_CHANNEL_ID = 1364075381669236828
ADMIN_ROLE_ID = 1391785348262264925

# --- DATA ---
work_data = {}
leaderboard_message = None
panel_message = None

class WorkPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        buttons = [
            ("Clock In", discord.ButtonStyle.success, "clock_in"),
            ("Clock Out", discord.ButtonStyle.danger, "clock_out"),
            ("Car Part", discord.ButtonStyle.primary, "car_part"),
            ("Bike Part", discord.ButtonStyle.primary, "bike_part"),
            ("Engine Upgrade", discord.ButtonStyle.primary, "engine_upgrade"),
            ("Full Car Upgrade", discord.ButtonStyle.secondary, "car_full"),
            ("Full Bike Upgrade", discord.ButtonStyle.secondary, "bike_full"),
            ("Repair", discord.ButtonStyle.primary, "repair"),
            ("Refresh Leaderboard", discord.ButtonStyle.secondary, "refresh"),
            ("Reset Leaderboard", discord.ButtonStyle.danger, "reset")
        ]
        for label, style, custom_id in buttons:
            self.add_item(discord.ui.Button(label=label, style=style, custom_id=custom_id))

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        await bot.tree.sync()
        print("Synced commands")

        guild = discord.Object(id=WORK_CHANNEL_ID)
        work_channel = bot.get_channel(WORK_CHANNEL_ID)
        leaderboard_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)

        if work_channel:
            global panel_message
            await work_channel.purge(limit=10)
            panel_message = await work_channel.send("**Work Panel**", view=WorkPanel())

        if leaderboard_channel:
            await leaderboard_channel.purge(limit=10)
            await update_leaderboard(leaderboard_channel)

    except Exception as e:
        print(f"Error in on_ready: {e}")

# --- LOGGING FIX ---
async def log_action(message: str):
    try:
        channel = await bot.fetch_channel(LOG_CHANNEL_ID)
        if channel:
            await channel.send(message)
    except Exception as e:
        print(f"Logging failed: {e}")

# --- BUTTON HANDLING ---
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.type == discord.InteractionType.component:
        return

    user_id = str(interaction.user.id)
    action = interaction.data["custom_id"]
    now = datetime.now(timezone.utc)

    if user_id not in work_data:
        work_data[user_id] = {
            "clocked_in": False,
            "last_clock_in": None,
            "parts": 0,
            "car_full": 0,
            "bike_full": 0,
            "engine": 0,
            "repair": 0,
            "total_time": timedelta()
        }

    user_data = work_data[user_id]

    if action == "clock_in":
        if user_data["clocked_in"]:
            await interaction.response.send_message("You’re already clocked in.", ephemeral=True)
            return
        user_data["clocked_in"] = True
        user_data["last_clock_in"] = now
        await log_action(f"{interaction.user.mention} Clocked In at {now.strftime('%Y-%m-%d %H:%M:%S')}")
        await interaction.response.send_message("Clocked In.", ephemeral=True)

    elif action == "clock_out":
        if not user_data["clocked_in"]:
            await interaction.response.send_message("You’re not clocked in.", ephemeral=True)
            return
        elapsed = now - user_data["last_clock_in"]
        user_data["total_time"] += elapsed
        user_data["clocked_in"] = False
        user_data["last_clock_in"] = None
        await log_action(f"{interaction.user.mention} Clocked Out after {str(elapsed)}")
        await interaction.response.send_message(f"Clocked Out. Time: {str(elapsed)}", ephemeral=True)

    elif action in ["car_part", "bike_part", "engine_upgrade", "car_full", "bike_full", "repair"]:
        if not user_data["clocked_in"]:
            await interaction.response.send_message("You must clock in first!", ephemeral=True)
            return

        if action == "car_part" or action == "bike_part":
            user_data["parts"] += 1
        elif action == "engine_upgrade":
            user_data["engine"] += 1
        elif action == "car_full":
            user_data["car_full"] += 1
        elif action == "bike_full":
            user_data["bike_full"] += 1
        elif action == "repair":
            user_data["repair"] += 1

        await log_action(f"{interaction.user.mention} performed {action.replace('_', ' ').title()} at {now.strftime('%Y-%m-%d %H:%M:%S')}")
        await interaction.response.send_message("Action logged.", ephemeral=True)

    elif action == "refresh":
        await update_leaderboard(bot.get_channel(LEADERBOARD_CHANNEL_ID))
        await interaction.response.send_message("Leaderboard refreshed.", ephemeral=True)

    elif action == "reset":
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("You don’t have permission.", ephemeral=True)
            return

        await confirm_reset(interaction)

# --- CONFIRM RESET ---
async def confirm_reset(interaction):
    class Confirm(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=30)
            self.value = None

        @discord.ui.button(label="Confirm Reset", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.value = True
            self.stop()

        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.value = False
            self.stop()

    view = Confirm()
    await interaction.response.send_message("Are you sure you want to reset the leaderboard?", view=view, ephemeral=True)
    await view.wait()

    if view.value:
        await backup_leaderboard()
        work_data.clear()
        await update_leaderboard(bot.get_channel(LEADERBOARD_CHANNEL_ID))
        await log_action(f"Leaderboard reset by {interaction.user.mention}")

# --- LEADERBOARD ---
async def update_leaderboard(channel):
    if not channel:
        return

    leaderboard = sorted(work_data.items(), key=lambda i: i[1]["total_time"], reverse=True)
    lines = []
    for uid, data in leaderboard:
        member = await bot.fetch_user(int(uid))
        name = member.name
        total_time = str(data["total_time"]).split(".")[0]
        parts = data["parts"]
        car_full = data["car_full"]
        bike_full = data["bike_full"]
        engine = data["engine"]
        repair = data["repair"]
        lines.append(
            f"**{name}**\n🕒 Time: {total_time} | 🧩 Parts: {parts} | 🛠 Engine: {engine} | 🚗 Car Full: {car_full} | 🏍 Bike Full: {bike_full} | 🔧 Repair: {repair}"
        )

    embed = discord.Embed(title="📊 Leaderboard", description="\n\n".join(lines) if lines else "No data yet.")
    global leaderboard_message
    if leaderboard_message:
        await leaderboard_message.edit(embed=embed, view=WorkPanel())
    else:
        leaderboard_message = await channel.send(embed=embed, view=WorkPanel())

# --- BACKUP ---
async def backup_leaderboard():
    lines = []
    for uid, data in work_data.items():
        user = await bot.fetch_user(int(uid))
        total_time = str(data["total_time"]).split(".")[0]
        lines.append(f"{user.name} | Time: {total_time} | Parts: {data['parts']} | Engine: {data['engine']} | Car Full: {data['car_full']} | Bike Full: {data['bike_full']} | Repair: {data['repair']}")

    content = "\n".join(lines) if lines else "No data to back up."
    channel = await bot.fetch_channel(BACKUP_CHANNEL_ID)
    await channel.send(f"**Monthly Backup - {datetime.now().strftime('%Y-%m-%d')}**\n```{content}```")

# --- ADMIN COMMANDS ---
@bot.tree.command(name="admin_set_clocked_on")
@app_commands.describe(user="User to set clocked in")
async def admin_set_clocked_on(interaction: discord.Interaction, user: discord.User):
    if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
        await interaction.response.send_message("You don’t have permission.", ephemeral=True)
        return
    uid = str(user.id)
    work_data[uid] = work_data.get(uid, {})
    work_data[uid]["clocked_in"] = True
    work_data[uid]["last_clock_in"] = datetime.now(timezone.utc)
    await interaction.response.send_message(f"{user.mention} is now clocked on.")

@bot.tree.command(name="admin_remove_parts")
@app_commands.describe(user="User to remove all parts/full upgrades/engine/repair")
async def admin_remove_parts(interaction: discord.Interaction, user: discord.User):
    if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
        await interaction.response.send_message("You don’t have permission.", ephemeral=True)
        return
    uid = str(user.id)
    work_data[uid] = {
        **work_data.get(uid, {}),
        "parts": 0,
        "car_full": 0,
        "bike_full": 0,
        "engine": 0,
        "repair": 0,
    }
    await interaction.response.send_message(f"Removed all part/upgrade data from {user.mention}.")

@bot.tree.command(name="admin_remove_time")
@app_commands.describe(user="User to remove time")
async def admin_remove_time(interaction: discord.Interaction, user: discord.User):
    if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
        await interaction.response.send_message("You don’t have permission.", ephemeral=True)
        return
    uid = str(user.id)
    work_data[uid]["total_time"] = timedelta()
    await interaction.response.send_message(f"Removed total time for {user.mention}.")

# --- RUN BOT ---
bot.run(os.getenv("DISCORD_TOKEN"))
