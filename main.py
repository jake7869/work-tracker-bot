import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction, ButtonStyle
from discord.ui import Button, View, Select
import asyncio
import os
from datetime import datetime, timedelta

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
TOKEN = os.getenv("DISCORD_TOKEN")

PANEL_CHANNEL_ID = 1344409201123786758
LEADERBOARD_CHANNEL_ID = 1364065995408281651
LOG_CHANNEL_ID = 1390028891791298731
ADMIN_ROLE_ID = 1391785348262264925

work_data = {}
panel_message = None
leaderboard_message = None

prices = {
    "car_part": 50000,
    "bike_part": 50000,
    "engine_upgrade": 500000,
    "full_car_upgrade": 850000,
    "full_bike_upgrade": 300000
}


def is_admin(interaction: Interaction):
    return any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)


async def log_action(message: str):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(message)


def get_user_data(user_id):
    if user_id not in work_data:
        work_data[user_id] = {
            "clocked_in": False,
            "last_clock_in": None,
            "total_time": timedelta(),
            "car_parts": 0,
            "bike_parts": 0,
            "engine_upgrades": 0,
            "full_car_upgrades": 0,
            "full_bike_upgrades": 0
        }
    return work_data[user_id]


async def update_leaderboard():
    global leaderboard_message
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return

    sorted_data = sorted(work_data.items(), key=lambda x: (
        x[1]["car_parts"] + x[1]["bike_parts"] + x[1]["engine_upgrades"] +
        x[1]["full_car_upgrades"] + x[1]["full_bike_upgrades"]), reverse=True)

    lines = []
    for user_id, data in sorted_data:
        total_earned = (
            data["car_parts"] * prices["car_part"]
            + data["bike_parts"] * prices["bike_part"]
            + data["engine_upgrades"] * prices["engine_upgrade"]
            + data["full_car_upgrades"] * prices["full_car_upgrade"]
            + data["full_bike_upgrades"] * prices["full_bike_upgrade"]
        )
        hours, remainder = divmod(int(data["total_time"].total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{hours}h {minutes}m"
        lines.append(
            f"<@{user_id}> - £{total_earned:,} | Car Parts: {data['car_parts']} | Bike Parts: {data['bike_parts']} | Engine Upgrades: {data['engine_upgrades']} | Full Car Upgrades: {data['full_car_upgrades']} | Full Bike Upgrades: {data['full_bike_upgrades']} | Time: {time_str}"
        )

    leaderboard = "\n".join(lines) or "*No data yet*"

    embed = discord.Embed(title="Work Leaderboard", description=leaderboard, color=discord.Color.blue())
    if leaderboard_message:
        await leaderboard_message.edit(embed=embed)
    else:
        leaderboard_message = await channel.send(embed=embed)


class WorkView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Clock In", style=ButtonStyle.success, custom_id="clock_in"))
        self.add_item(Button(label="Clock Out", style=ButtonStyle.danger, custom_id="clock_out"))
        self.add_item(Button(label="Car Part", style=ButtonStyle.primary, custom_id="car_part"))
        self.add_item(Button(label="Bike Part", style=ButtonStyle.primary, custom_id="bike_part"))
        self.add_item(Button(label="Engine Upgrade", style=ButtonStyle.primary, custom_id="engine_upgrade"))
        self.add_item(Button(label="Full Car Upgrade", style=ButtonStyle.secondary, custom_id="full_car_upgrade"))
        self.add_item(Button(label="Full Bike Upgrade", style=ButtonStyle.secondary, custom_id="full_bike_upgrade"))
        self.add_item(Button(label="Repair", style=ButtonStyle.primary, custom_id="repair"))
        self.add_item(Button(label="Refresh Leaderboard", style=ButtonStyle.secondary, custom_id="refresh"))
        self.add_item(Button(label="Reset Leaderboard", style=ButtonStyle.danger, custom_id="reset_leaderboard"))

    async def interaction_check(self, interaction: Interaction) -> bool:
        return True

    @discord.ui.button(label="Clock In", style=ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: Interaction, button: Button):
        user_id = str(interaction.user.id)
        data = get_user_data(user_id)
        if data["clocked_in"]:
            await interaction.response.send_message("You're already clocked in!", ephemeral=True)
            return
        data["clocked_in"] = True
        data["last_clock_in"] = datetime.utcnow()
        await log_action(f"{interaction.user.mention} Clocked In at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
        await interaction.response.send_message("You have clocked in.", ephemeral=True)

    @discord.ui.button(label="Clock Out", style=ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: Interaction, button: Button):
        user_id = str(interaction.user.id)
        data = get_user_data(user_id)
        if not data["clocked_in"]:
            await interaction.response.send_message("You're not clocked in!", ephemeral=True)
            return
        session_time = datetime.utcnow() - data["last_clock_in"]
        data["total_time"] += session_time
        data["clocked_in"] = False
        data["last_clock_in"] = None
        await log_action(f"{interaction.user.mention} Clocked Out at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} (Session: {str(session_time).split('.')[0]})")
        await interaction.response.send_message("You have clocked out.", ephemeral=True)
        await update_leaderboard()

    async def handle_work(self, interaction: Interaction, action: str):
        user_id = str(interaction.user.id)
        data = get_user_data(user_id)
        if not data["clocked_in"]:
            await interaction.response.send_message("You must be clocked in to log work!", ephemeral=True)
            return

        if action == "car_part":
            data["car_parts"] += 1
        elif action == "bike_part":
            data["bike_parts"] += 1
        elif action == "engine_upgrade":
            data["engine_upgrades"] += 1
        elif action == "full_car_upgrade":
            data["full_car_upgrades"] += 1
        elif action == "full_bike_upgrade":
            data["full_bike_upgrades"] += 1

        await interaction.response.send_message(f"{action.replace('_', ' ').title()} logged!", ephemeral=True)
        await log_action(f"{interaction.user.mention} logged a {action.replace('_', ' ').title()} at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
        await update_leaderboard()

    @discord.ui.button(label="Car Part", style=ButtonStyle.primary, custom_id="car_part")
    async def car_part(self, interaction: Interaction, button: Button):
        await self.handle_work(interaction, "car_part")

    @discord.ui.button(label="Bike Part", style=ButtonStyle.primary, custom_id="bike_part")
    async def bike_part(self, interaction: Interaction, button: Button):
        await self.handle_work(interaction, "bike_part")

    @discord.ui.button(label="Engine Upgrade", style=ButtonStyle.primary, custom_id="engine_upgrade")
    async def engine_upgrade(self, interaction: Interaction, button: Button):
        await self.handle_work(interaction, "engine_upgrade")

    @discord.ui.button(label="Full Car Upgrade", style=ButtonStyle.secondary, custom_id="full_car_upgrade")
    async def full_car_upgrade(self, interaction: Interaction, button: Button):
        await self.handle_work(interaction, "full_car_upgrade")

    @discord.ui.button(label="Full Bike Upgrade", style=ButtonStyle.secondary, custom_id="full_bike_upgrade")
    async def full_bike_upgrade(self, interaction: Interaction, button: Button):
        await self.handle_work(interaction, "full_bike_upgrade")

    @discord.ui.button(label="Repair", style=ButtonStyle.primary, custom_id="repair")
    async def repair(self, interaction: Interaction, button: Button):
        await self.handle_work(interaction, "car_part")

    @discord.ui.button(label="Refresh Leaderboard", style=ButtonStyle.secondary, custom_id="refresh")
    async def refresh(self, interaction: Interaction, button: Button):
        await update_leaderboard()
        await interaction.response.send_message("Leaderboard refreshed!", ephemeral=True)

    @discord.ui.button(label="Reset Leaderboard", style=ButtonStyle.danger, custom_id="reset_leaderboard")
    async def reset_leaderboard(self, interaction: Interaction, button: Button):
        if not is_admin(interaction):
            await interaction.response.send_message("You do not have permission to reset the leaderboard.", ephemeral=True)
            return
        await interaction.response.send_message("Are you sure you want to reset the leaderboard?", ephemeral=True)

        async def confirm_callback(inter: Interaction):
            work_data.clear()
            await update_leaderboard()
            await log_action(f"{interaction.user.mention} reset the leaderboard.")
            await inter.response.edit_message(content="Leaderboard has been reset.", view=None)

        async def cancel_callback(inter: Interaction):
            await inter.response.edit_message(content="Reset cancelled.", view=None)

        view = View()
        view.add_item(Button(label="Yes", style=ButtonStyle.danger, custom_id="confirm_reset"))
        view.add_item(Button(label="No", style=ButtonStyle.secondary, custom_id="cancel_reset"))

        async def interaction_check(inner: Interaction):
            return inner.user == interaction.user

        view.children[0].callback = confirm_callback
        view.children[1].callback = cancel_callback
        await interaction.followup.send("Are you sure?", view=view, ephemeral=True)


@bot.event
async def on_ready():
    global panel_message
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    bot.add_view(WorkView())

    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    leaderboard_channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if panel_channel:
        async for msg in panel_channel.history(limit=10):
            if msg.author == bot.user and msg.components:
                panel_message = msg
                await panel_message.edit(view=WorkView())
                break
        else:
            panel_message = await panel_channel.send("**Work Panel**", view=WorkView())

    if leaderboard_channel:
        async for msg in leaderboard_channel.history(limit=10):
            if msg.author == bot.user and msg.embeds:
                global leaderboard_message
                leaderboard_message = msg
                break
        else:
            leaderboard_message = await leaderboard_channel.send("Loading leaderboard...")
        await update_leaderboard()


bot.run(TOKEN)
