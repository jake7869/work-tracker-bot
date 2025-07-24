import os
import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction, ButtonStyle, SelectOption
from discord.ui import View, Button, Select
from datetime import datetime, timedelta
from collections import defaultdict

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")

PANEL_CHANNEL_ID = 1344409201123786758
LOG_CHANNEL_ID = 1390028891791298731
LEADERBOARD_CHANNEL_ID = 1364065995408281651
ADMIN_ROLE_ID = 1391785348262264925

user_data = defaultdict(lambda: {
    "clocked_in": False,
    "start_time": None,
    "total_time": timedelta(),
    "car_parts": 0,
    "bike_parts": 0,
    "car_upgrades": 0,
    "bike_upgrades": 0,
    "engine_upgrades": 0
})

PRICES = {
    "car_parts": 50000,
    "bike_parts": 50000,
    "car_upgrades": 850000,
    "bike_upgrades": 300000,
    "engine_upgrades": 500000
}

def format_duration(td):
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}:{minutes:02}:{seconds:02}"

async def log_action(message: str):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(message)

async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return
    leaderboard = sorted(user_data.items(), key=lambda x: sum(x[1][k] * PRICES[k] for k in PRICES), reverse=True)

    description = ""
    total_money = 0
    for user_id, data in leaderboard:
        earned = sum(data[k] * PRICES[k] for k in PRICES)
        total_money += earned
        member = await bot.fetch_user(user_id)
        description += (
            f"**{member.name if member else user_id}**\n"
            f"Time: {format_duration(data['total_time'])}\n"
            f"Car Parts: {data['car_parts']}\n"
            f"Bike Parts: {data['bike_parts']}\n"
            f"Car Upgrades: {data['car_upgrades']}\n"
            f"Bike Upgrades: {data['bike_upgrades']}\n"
            f"Engine Upgrades: {data['engine_upgrades']}\n"
            f"**Total Earned:** £{earned:,}\n\n"
        )

    embed = discord.Embed(title="🏆 Work Leaderboard", description=description)
    embed.set_footer(text=f"Total Money Earned: £{total_money:,}")
    messages = [m async for m in channel.history(limit=5)]
    if messages:
        await messages[0].edit(embed=embed)
    else:
        await channel.send(embed=embed)

class WorkButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(WorkDropdown())
        self.add_item(AdminDropdown())

    @discord.ui.button(label="Clock In", style=ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: Interaction, _):
        user = interaction.user
        data = user_data[user.id]
        if not data["clocked_in"]:
            data["clocked_in"] = True
            data["start_time"] = datetime.utcnow()
            await interaction.response.send_message(f"✅ {user.mention} clocked in!", ephemeral=True)
            await log_action(f"📝 {user.mention} clocked in at {data['start_time']}")
        else:
            await interaction.response.send_message("You are already clocked in.", ephemeral=True)

    @discord.ui.button(label="Clock Out", style=ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: Interaction, _):
        user = interaction.user
        data = user_data[user.id]
        if data["clocked_in"]:
            duration = datetime.utcnow() - data["start_time"]
            data["total_time"] += duration
            data["clocked_in"] = False
            await interaction.response.send_message(f"🕒 {user.mention} clocked out after {format_duration(duration)}", ephemeral=True)
            await log_action(f"📝 {user.mention} clocked out at {datetime.utcnow()} — Session: {format_duration(duration)}")
            await update_leaderboard()
        else:
            await interaction.response.send_message("You are not clocked in.", ephemeral=True)

    async def track_action(self, interaction, field, label):
        user = interaction.user
        data = user_data[user.id]
        if not data["clocked_in"]:
            await interaction.response.send_message("❌ You must clock in first!", ephemeral=True)
            return
        data[field] += 1
        await interaction.response.send_message(f"✅ Logged {label}", ephemeral=True)
        await log_action(f"🛠️ {user.mention} completed **{label}** at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
        await update_leaderboard()

    @discord.ui.button(label="Car Part", style=ButtonStyle.primary, custom_id="car_part")
    async def car_part(self, interaction: Interaction, _):
        await self.track_action(interaction, "car_parts", "Car Part")

    @discord.ui.button(label="Bike Part", style=ButtonStyle.primary, custom_id="bike_part")
    async def bike_part(self, interaction: Interaction, _):
        await self.track_action(interaction, "bike_parts", "Bike Part")

    @discord.ui.button(label="Car Full Upgrade", style=ButtonStyle.secondary, custom_id="car_upgrade")
    async def car_upgrade(self, interaction: Interaction, _):
        await self.track_action(interaction, "car_upgrades", "Car Full Upgrade")

    @discord.ui.button(label="Bike Full Upgrade", style=ButtonStyle.secondary, custom_id="bike_upgrade")
    async def bike_upgrade(self, interaction: Interaction, _):
        await self.track_action(interaction, "bike_upgrades", "Bike Full Upgrade")

    @discord.ui.button(label="Engine Upgrade", style=ButtonStyle.secondary, custom_id="engine_upgrade")
    async def engine_upgrade(self, interaction: Interaction, _):
        await self.track_action(interaction, "engine_upgrades", "Engine Upgrade")

    @discord.ui.button(label="Reset Leaderboard", style=ButtonStyle.danger, custom_id="reset")
    async def reset_button(self, interaction: Interaction, _):
        if ADMIN_ROLE_ID in [role.id for role in interaction.user.roles]:
            user_data.clear()
            await update_leaderboard()
            await interaction.response.send_message("✅ Leaderboard reset.", ephemeral=True)
            await log_action(f"🧹 {interaction.user.mention} reset the leaderboard.")
        else:
            await interaction.response.send_message("⛔ You don't have permission.", ephemeral=True)

    @discord.ui.button(label="Refresh Leaderboard", style=ButtonStyle.primary, custom_id="refresh")
    async def refresh_button(self, interaction: Interaction, _):
        await update_leaderboard()
        await interaction.response.send_message("🔄 Leaderboard refreshed!", ephemeral=True)

class WorkDropdown(Select):
    def __init__(self):
        options = [
            SelectOption(label="Force Clock Out", value="clockout"),
            SelectOption(label="Remove Car Upgrade", value="car_upgrade"),
            SelectOption(label="Remove Bike Upgrade", value="bike_upgrade"),
            SelectOption(label="Remove Engine Upgrade", value="engine_upgrade"),
            SelectOption(label="Remove Car Part", value="car_part"),
            SelectOption(label="Remove Bike Part", value="bike_part"),
            SelectOption(label="Remove Time", value="remove_time")
        ]
        super().__init__(placeholder="Admin Controls", options=options, custom_id="admin_dropdown")

    async def callback(self, interaction: Interaction):
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("You don't have permission.", ephemeral=True)
            return

        members = [SelectOption(label=member.name, value=str(member.id)) async for member in interaction.guild.fetch_members(limit=100)]
        await interaction.response.send_message("Choose user to modify:", view=AdminDropdownAction(self.values[0], members), ephemeral=True)

class AdminDropdown(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

class AdminDropdownAction(View):
    def __init__(self, action_type, members):
        super().__init__(timeout=30)
        self.add_item(UserTargetSelect(action_type, members))

class UserTargetSelect(Select):
    def __init__(self, action_type, members):
        self.action_type = action_type
        super().__init__(placeholder="Select member...", options=members)

    async def callback(self, interaction: Interaction):
        target_id = int(self.values[0])
        if target_id not in user_data:
            await interaction.response.send_message("User has no data.", ephemeral=True)
            return
        if self.action_type == "clockout":
            user_data[target_id]["clocked_in"] = False
            await log_action(f"⛔ Forced clock out for <@{target_id}>")
        elif self.action_type == "remove_time":
            user_data[target_id]["total_time"] = timedelta()
        else:
            field = self.action_type
            user_data[target_id][field] = max(0, user_data[target_id][field] - 1)
            await log_action(f"🧾 Admin removed one **{field.replace('_', ' ').title()}** from <@{target_id}>")

        await update_leaderboard()
        await interaction.response.send_message("✅ Action completed.", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if channel:
        await channel.purge()
        await channel.send("**Work Tracker Panel**", view=WorkButtons())
    await update_leaderboard()

bot.run(TOKEN)
