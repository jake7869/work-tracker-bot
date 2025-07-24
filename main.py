import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

panel_channel_id = 1344409201123786758
log_channel_id = 1390028891791298731
leaderboard_channel_id = 1364065995408281651
admin_role_id = 1391785348262264925

work_data = {}
clocked_in_users = {}

BUTTON_IDS = {
    "clock_in": "clockin_btn",
    "clock_out": "clockout_btn",
    "car_part": "carpart_btn",
    "bike_part": "bikepart_btn",
    "car_upgrade": "carupgrade_btn",
    "bike_upgrade": "bikeupgrade_btn",
    "engine_upgrade": "engineupgrade_btn",
    "reset": "reset_btn",
    "refresh": "refresh_btn"
}

TASK_REWARDS = {
    "Car Part": 50000,
    "Bike Part": 50000,
    "Car Full Upgrade": 850000,
    "Bike Full Upgrade": 300000,
    "Engine Upgrade": 500000
}


async def log_action(message):
    channel = bot.get_channel(log_channel_id)
    if channel:
        await channel.send(message)


def is_admin(interaction: discord.Interaction) -> bool:
    return any(role.id == admin_role_id for role in interaction.user.roles)


class WorkButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Clock In", style=discord.ButtonStyle.success, custom_id=BUTTON_IDS["clock_in"]))
        self.add_item(discord.ui.Button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id=BUTTON_IDS["clock_out"]))
        self.add_item(discord.ui.Button(label="Car Part", style=discord.ButtonStyle.primary, custom_id=BUTTON_IDS["car_part"]))
        self.add_item(discord.ui.Button(label="Bike Part", style=discord.ButtonStyle.primary, custom_id=BUTTON_IDS["bike_part"]))
        self.add_item(discord.ui.Button(label="Car Full Upgrade", style=discord.ButtonStyle.secondary, custom_id=BUTTON_IDS["car_upgrade"]))
        self.add_item(discord.ui.Button(label="Bike Full Upgrade", style=discord.ButtonStyle.secondary, custom_id=BUTTON_IDS["bike_upgrade"]))
        self.add_item(discord.ui.Button(label="Engine Upgrade", style=discord.ButtonStyle.secondary, custom_id=BUTTON_IDS["engine_upgrade"]))
        self.add_item(discord.ui.Button(label="Reset Leaderboard", style=discord.ButtonStyle.danger, custom_id=BUTTON_IDS["reset"]))
        self.add_item(discord.ui.Button(label="Refresh Leaderboard", style=discord.ButtonStyle.primary, custom_id=BUTTON_IDS["refresh"]))


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    channel = bot.get_channel(panel_channel_id)
    if channel:
        try:
            await channel.purge(limit=10)
            await channel.send("**Work Tracker Panel**", view=WorkButtons())
        except Exception as e:
            print(f"Failed to send panel message: {e}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.event
async def on_interaction(interaction: discord.Interaction):
    custom_id = getattr(interaction.data, "custom_id", None)
    if custom_id in BUTTON_IDS.values():
        await handle_button_click(interaction)


async def handle_button_click(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    username = interaction.user.display_name

    if user_id not in work_data:
        work_data[user_id] = {
            "clock_in": None,
            "clocked_time": timedelta(),
            "Car Part": 0,
            "Bike Part": 0,
            "Car Full Upgrade": 0,
            "Bike Full Upgrade": 0,
            "Engine Upgrade": 0,
        }

    btn_id = interaction.data["custom_id"]

    if btn_id == BUTTON_IDS["clock_in"]:
        work_data[user_id]["clock_in"] = datetime.utcnow()
        await interaction.response.send_message("Clocked in successfully!", ephemeral=True)
        await log_action(f"📝 <@{user_id}> clocked in at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

    elif btn_id == BUTTON_IDS["clock_out"]:
        clock_in_time = work_data[user_id]["clock_in"]
        if clock_in_time:
            duration = datetime.utcnow() - clock_in_time
            work_data[user_id]["clocked_time"] += duration
            work_data[user_id]["clock_in"] = None
            await interaction.response.send_message("Clocked out successfully.", ephemeral=True)
            await log_action(f"📝 <@{user_id}> clocked out at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} (Session: {str(duration).split('.')[0]})")
        else:
            await interaction.response.send_message("You're not clocked in.", ephemeral=True)

    elif btn_id in [
        BUTTON_IDS["car_part"],
        BUTTON_IDS["bike_part"],
        BUTTON_IDS["car_upgrade"],
        BUTTON_IDS["bike_upgrade"],
        BUTTON_IDS["engine_upgrade"]
    ]:
        task_name = {
            BUTTON_IDS["car_part"]: "Car Part",
            BUTTON_IDS["bike_part"]: "Bike Part",
            BUTTON_IDS["car_upgrade"]: "Car Full Upgrade",
            BUTTON_IDS["bike_upgrade"]: "Bike Full Upgrade",
            BUTTON_IDS["engine_upgrade"]: "Engine Upgrade",
        }[btn_id]
        work_data[user_id][task_name] += 1
        await interaction.response.send_message(f"{task_name} recorded!", ephemeral=True)
        await log_action(f"📝 <@{user_id}> completed **{task_name}** at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

    elif btn_id == BUTTON_IDS["reset"]:
        if not is_admin(interaction):
            await interaction.response.send_message("You don’t have permission to reset.", ephemeral=True)
            return
        work_data.clear()
        await interaction.response.send_message("Leaderboard has been reset.", ephemeral=True)
        await log_action("🧨 Leaderboard manually reset.")

    elif btn_id == BUTTON_IDS["refresh"]:
        await send_leaderboard()
        await interaction.response.send_message("Leaderboard refreshed.", ephemeral=True)


async def send_leaderboard():
    channel = bot.get_channel(leaderboard_channel_id)
    if not channel:
        return

    sorted_users = sorted(work_data.items(), key=lambda x: sum(
        x[1][task] * TASK_REWARDS[task] for task in TASK_REWARDS
    ), reverse=True)

    embed = discord.Embed(title="📊 Work Leaderboard", color=discord.Color.green())

    total_earned_all = 0
    for user_id, data in sorted_users:
        total = sum(data[task] * TASK_REWARDS[task] for task in TASK_REWARDS)
        total_earned_all += total
        time_str = str(data["clocked_time"]).split(".")[0]
        member = await bot.fetch_user(int(user_id))
        embed.add_field(
            name=f"👤 {member.display_name}",
            value=(
                f"**Time:** {time_str}\n"
                f"**Car Parts:** {data['Car Part']}\n"
                f"**Bike Parts:** {data['Bike Part']}\n"
                f"**Car Upgrades:** {data['Car Full Upgrade']}\n"
                f"**Bike Upgrades:** {data['Bike Full Upgrade']}\n"
                f"**Engine Upgrades:** {data['Engine Upgrade']}\n"
                f"**Total Earned:** £{total:,}"
            ),
            inline=False
        )

    embed.set_footer(text=f"💰 Total Earned by All: £{total_earned_all:,}")
    await channel.purge(limit=1)
    await channel.send(embed=embed)


@bot.tree.command(name="set_clockin", description="Admin only: Set a user as clocked in now.")
@app_commands.checks.has_role(admin_role_id)
@app_commands.describe(member="The member to clock in")
async def set_clockin(interaction: discord.Interaction, member: discord.Member):
    user_id = str(member.id)
    if user_id not in work_data:
        work_data[user_id] = {
            "clock_in": None,
            "clocked_time": timedelta(),
            "Car Part": 0,
            "Bike Part": 0,
            "Car Full Upgrade": 0,
            "Bike Full Upgrade": 0,
            "Engine Upgrade": 0,
        }
    work_data[user_id]["clock_in"] = datetime.utcnow()
    await interaction.response.send_message(f"{member.display_name} manually clocked in.", ephemeral=True)
    await log_action(f"🛠️ {interaction.user.mention} manually clocked in {member.mention}")


# Add other admin commands here if needed (remove part, remove upgrade, remove time, etc)

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
