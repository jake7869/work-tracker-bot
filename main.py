import discord
from discord.ext import commands, tasks
from discord.ui import View, Button, Select
from datetime import datetime, timedelta
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")

PANEL_CHANNEL_ID = 1344409201123786758
LOG_CHANNEL_ID = 1390028891791298731
LEADERBOARD_CHANNEL_ID = 1364065995408281651
ADMIN_ROLE_ID = 1391785348262264925

user_data = {}
panel_message = None
leaderboard_message = None

PRICES = {
    "Car Part": 50000,
    "Bike Part": 50000,
    "Car Full Upgrade": 850000,
    "Bike Full Upgrade": 300000,
    "Engine Upgrade": 500000,
}

def format_time(seconds):
    return str(timedelta(seconds=seconds))

def build_leaderboard_embed():
    embed = discord.Embed(title="📊 Work Leaderboard", color=discord.Color.gold())
    total_earned = 0

    for user_id, data in sorted(user_data.items(), key=lambda x: sum(PRICES[k] * v for k, v in x[1]['tasks'].items()), reverse=True):
        user_mention = f"<@{user_id}>"
        task_counts = "\n".join([f"**{task}s:** {count}" for task, count in data['tasks'].items()])
        earned = sum(PRICES[task] * count for task, count in data['tasks'].items())
        total_earned += earned

        embed.add_field(
            name=user_mention,
            value=f"**Time:** {format_time(data.get('total_time', 0))}\n{task_counts}\n**Total Earned:** £{earned:,}",
            inline=False
        )

    embed.set_footer(text=f"Total Money Earned: £{total_earned:,}")
    return embed

async def update_leaderboard():
    global leaderboard_message
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if leaderboard_message:
        await leaderboard_message.edit(embed=build_leaderboard_embed())
    else:
        leaderboard_message = await channel.send(embed=build_leaderboard_embed())

async def log_action(user, action_type):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    await channel.send(f"📝 {user.mention} completed **{action_type}** at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

async def handle_task(interaction, task_name):
    user_id = interaction.user.id
    if user_id not in user_data:
        user_data[user_id] = {"clock_in": None, "total_time": 0, "tasks": {k: 0 for k in PRICES}}

    user_data[user_id]["tasks"][task_name] += 1
    await log_action(interaction.user, task_name)
    await interaction.response.send_message(f"✅ {task_name} recorded!", ephemeral=True)
    await update_leaderboard()

class WorkButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        for task in ["Car Part", "Bike Part", "Car Full Upgrade", "Bike Full Upgrade", "Engine Upgrade"]:
            self.add_item(WorkButton(label=task))

        self.add_item(ClockButton("Clock In", True))
        self.add_item(ClockButton("Clock Out", False))
        self.add_item(AdminControlDropdown())

class WorkButton(Button):
    def __init__(self, label):
        super().__init__(style=discord.ButtonStyle.blurple, label=label, custom_id=label)

    async def callback(self, interaction):
        await handle_task(interaction, self.label)

class ClockButton(Button):
    def __init__(self, label, clocking_in):
        super().__init__(style=discord.ButtonStyle.success if clocking_in else discord.ButtonStyle.danger, label=label, custom_id=label)
        self.clocking_in = clocking_in

    async def callback(self, interaction):
        user_id = interaction.user.id
        if user_id not in user_data:
            user_data[user_id] = {"clock_in": None, "total_time": 0, "tasks": {k: 0 for k in PRICES}}

        if self.clocking_in:
            user_data[user_id]["clock_in"] = datetime.utcnow()
            await log_action(interaction.user, "Clock In")
            await interaction.response.send_message("🕒 Clocked in!", ephemeral=True)
        else:
            clocked_in = user_data[user_id].get("clock_in")
            if clocked_in:
                elapsed = (datetime.utcnow() - clocked_in).total_seconds()
                user_data[user_id]["total_time"] += int(elapsed)
                user_data[user_id]["clock_in"] = None
                await log_action(interaction.user, "Clock Out")
                await interaction.response.send_message(f"✅ Clocked out! Time added: {format_time(int(elapsed))}", ephemeral=True)
                await update_leaderboard()
            else:
                await interaction.response.send_message("❌ You weren't clocked in!", ephemeral=True)

class AdminControlDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Force Clock Out", value="force_clock_out"),
            discord.SelectOption(label="Remove Car Part", value="remove_car_part"),
            discord.SelectOption(label="Remove Bike Part", value="remove_bike_part"),
            discord.SelectOption(label="Remove Car Full Upgrade", value="remove_car_upgrade"),
            discord.SelectOption(label="Remove Bike Full Upgrade", value="remove_bike_upgrade"),
            discord.SelectOption(label="Remove Engine Upgrade", value="remove_engine_upgrade"),
            discord.SelectOption(label="Remove Time", value="remove_time")
        ]
        super().__init__(placeholder="⚙️ Admin Controls", min_values=1, max_values=1, options=options, custom_id="admin_controls")

    async def callback(self, interaction: discord.Interaction):
        if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("❌ You do not have permission to use this!", ephemeral=True)
            return

        members = [m for m in interaction.guild.members if not m.bot]
        select = AdminTargetDropdown(self.values[0], members)
        await interaction.response.send_message("Select a member:", view=select, ephemeral=True)

class AdminTargetDropdown(View):
    def __init__(self, action, members):
        super().__init__(timeout=30)
        self.add_item(AdminUserDropdown(action, members))

class AdminUserDropdown(Select):
    def __init__(self, action, members):
        self.action = action
        options = [discord.SelectOption(label=member.name, value=str(member.id)) for member in members]
        super().__init__(placeholder="Select user...", options=options)

    async def callback(self, interaction):
        uid = int(self.values[0])
        user = user_data.get(uid)
        if not user:
            await interaction.response.send_message("❌ User not found in data.", ephemeral=True)
            return

        if self.action == "force_clock_out":
            clocked_in = user.get("clock_in")
            if clocked_in:
                elapsed = (datetime.utcnow() - clocked_in).total_seconds()
                user["total_time"] += int(elapsed)
                user["clock_in"] = None
                await interaction.response.send_message(f"⏹ Forced clock out. Time added: {format_time(int(elapsed))}", ephemeral=True)
            else:
                await interaction.response.send_message("User was not clocked in.", ephemeral=True)

        elif self.action.startswith("remove_"):
            task_map = {
                "remove_car_part": "Car Part",
                "remove_bike_part": "Bike Part",
                "remove_car_upgrade": "Car Full Upgrade",
                "remove_bike_upgrade": "Bike Full Upgrade",
                "remove_engine_upgrade": "Engine Upgrade"
            }
            task = task_map.get(self.action)
            if task and user["tasks"].get(task, 0) > 0:
                user["tasks"][task] -= 1
                await interaction.response.send_message(f"➖ Removed 1x {task} from <@{uid}>", ephemeral=True)
            elif self.action == "remove_time":
                user["total_time"] = max(0, user["total_time"] - 3600)
                await interaction.response.send_message("🕒 Removed 1 hour from total time.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Nothing to remove.", ephemeral=True)

        await update_leaderboard()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    global panel_message
    await panel_channel.purge(limit=5)
    panel_message = await panel_channel.send("**Work Tracker Panel**", view=WorkButtons())
    await update_leaderboard()

bot.run(TOKEN)
