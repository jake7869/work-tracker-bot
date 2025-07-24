import discord
from discord.ext import commands
from datetime import datetime, timedelta
from collections import defaultdict
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

work_data = defaultdict(lambda: {
    "clocked_in": False,
    "last_clock_in": None,
    "car": 0,
    "bike": 0,
    "engine": 0,
    "car_full": 0,
    "bike_full": 0,
    "repair": 0,
    "earnings": 0,
    "total_time": 0
})

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ADMIN_ROLE_ID = 1391785348262264925

PRICE_CONFIG = {
    "car": 50000,
    "bike": 50000,
    "engine": 500000,
    "car_full": 850000,
    "bike_full": 300000,
    "repair": 25000
}

TASK_LABELS = {
    "car": "Car Part",
    "bike": "Bike Part",
    "engine": "Engine Upgrade",
    "car_full": "Full Car Upgrade",
    "bike_full": "Full Bike Upgrade",
    "repair": "Repair"
}

class WorkPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(AdminDropdown())
        self.add_item(ResetRefreshButtons())

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You are already clocked in.", ephemeral=True)
            return
        work_data[user_id]["clocked_in"] = True
        work_data[user_id]["last_clock_in"] = datetime.utcnow()
        await interaction.response.send_message("✅ You clocked in!", ephemeral=True)
        await log_action(f"✅ **{interaction.user.name}** clocked in.")

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if not work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You are not clocked in.", ephemeral=True)
            return
        duration = (datetime.utcnow() - work_data[user_id]["last_clock_in"]).total_seconds()
        work_data[user_id]["total_time"] += duration
        work_data[user_id]["clocked_in"] = False
        work_data[user_id]["last_clock_in"] = None
        await interaction.response.send_message("⏹️ You clocked out.", ephemeral=True)
        await log_action(f"⏹️ **{interaction.user.name}** clocked out.")

    async def handle_action(self, interaction, action):
        user_id = str(interaction.user.id)
        if not work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You must clock in first.", ephemeral=True)
            return
        work_data[user_id][action] += 1
        work_data[user_id]["earnings"] += PRICE_CONFIG[action]
        await interaction.response.send_message(f"✅ {TASK_LABELS[action]} logged.", ephemeral=True)
        await log_action(f"🛠️ **{interaction.user.name}** completed **{TASK_LABELS[action]}**.")
        await update_leaderboard()

    @discord.ui.button(label="Car Part", style=discord.ButtonStyle.primary, custom_id="car")
    async def car(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car")

    @discord.ui.button(label="Bike Part", style=discord.ButtonStyle.primary, custom_id="bike")
    async def bike(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "bike")

    @discord.ui.button(label="Engine Upgrade", style=discord.ButtonStyle.primary, custom_id="engine")
    async def engine(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "engine")

    @discord.ui.button(label="Full Car Upgrade", style=discord.ButtonStyle.secondary, custom_id="car_full")
    async def car_full(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car_full")

    @discord.ui.button(label="Full Bike Upgrade", style=discord.ButtonStyle.secondary, custom_id="bike_full")
    async def bike_full(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "bike_full")

    @discord.ui.button(label="Repair", style=discord.ButtonStyle.secondary, custom_id="repair")
    async def repair(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "repair")

class AdminDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Force Clock Out", value="force_clockout"),
            discord.SelectOption(label="Remove Car Parts", value="remove_car"),
            discord.SelectOption(label="Remove Bike Parts", value="remove_bike"),
            discord.SelectOption(label="Remove Full Car Upgrades", value="remove_car_full"),
            discord.SelectOption(label="Remove Full Bike Upgrades", value="remove_bike_full"),
            discord.SelectOption(label="Remove Engine Upgrades", value="remove_engine"),
            discord.SelectOption(label="Remove Repair", value="remove_repair"),
            discord.SelectOption(label="Remove Time", value="remove_time")
        ]
        super().__init__(placeholder="Admin Tools", min_values=1, max_values=1, options=options, custom_id="admin_tools")

    async def callback(self, interaction: discord.Interaction):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("You do not have permission to use this.", ephemeral=True)
            return
        await interaction.response.send_message("Please enter the user ID and amount (if needed) in this format:\n`user_id amount`", ephemeral=True)

class ResetRefreshButtons(discord.ui.View):
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, custom_id="refresh")
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_leaderboard()
        await interaction.response.send_message("Leaderboard refreshed.", ephemeral=True)

    @discord.ui.button(label="Reset Leaderboard", style=discord.ButtonStyle.danger, custom_id="reset_leaderboard")
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("You do not have permission.", ephemeral=True)
            return
        work_data.clear()
        await update_leaderboard()
        await interaction.response.send_message("Leaderboard reset.", ephemeral=True)
        await log_action("🧹 **Leaderboard was reset by an admin.**")

async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return

    leaderboard = sorted(work_data.items(), key=lambda x: x[1]["earnings"], reverse=True)
    embed = discord.Embed(title="🏆 Work Leaderboard", color=discord.Color.gold())

    total_earned = 0
    for user_id, data in leaderboard:
        try:
            user = await bot.fetch_user(int(user_id))
            user_name = user.name
        except:
            user_name = f"<@{user_id}>"
        total_earned += data["earnings"]
        time_str = str(timedelta(seconds=int(data["total_time"])))
        embed.add_field(
            name=user_name,
            value=(
                f"🚗 Car: {data['car']} | 🛵 Bike: {data['bike']}\n"
                f"🛠️ Engine: {data['engine']} | 🚙 Car Full: {data['car_full']} | 🏍️ Bike Full: {data['bike_full']} | 🔧 Repair: {data['repair']}\n"
                f"💳 Earnings: £{data['earnings']:,}\n"
                f"⏱️ Time Clocked: {time_str}"
            ),
            inline=False
        )

    embed.set_footer(text=f"💰 Total Earned: £{total_earned:,}")
    async for msg in channel.history(limit=5):
        if msg.author == bot.user:
            await msg.delete()
    await channel.send(embed=embed)

async def log_action(message: str):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(message)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    view = WorkPanel()
    bot.add_view(view)
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        async for msg in panel_channel.history(limit=10):
            if msg.author == bot.user:
                await msg.delete()
        await panel_channel.send("**Work Panel**", view=view)

bot.run(DISCORD_BOT_TOKEN)
