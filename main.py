
import discord
from discord.ext import commands, tasks
import os
from datetime import datetime, timedelta
from collections import defaultdict

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
    "total_time": 0,
    "strikes": 0
})

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))

PRICE_CONFIG = {
    "car": 50000,
    "bike": 50000,
    "engine": 500000,
    "car_full": 850000,
    "bike_full": 300000,
    "repair": 25000
}

class AdminDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Force Clock Out", value="force_clock_out"),
            discord.SelectOption(label="Remove Car Upgrade", value="remove_car"),
            discord.SelectOption(label="Remove Bike Upgrade", value="remove_bike"),
            discord.SelectOption(label="Remove Engine Upgrade", value="remove_engine"),
            discord.SelectOption(label="Remove Full Car Upgrade", value="remove_car_full"),
            discord.SelectOption(label="Remove Full Bike Upgrade", value="remove_bike_full"),
            discord.SelectOption(label="Remove Repair", value="remove_repair"),
            discord.SelectOption(label="Remove Time (in minutes)", value="remove_time")
        ]
        super().__init__(placeholder="Admin Actions", options=options, custom_id="admin_dropdown")

    async def callback(self, interaction: discord.Interaction):
        if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("You don't have permission to use this.", ephemeral=True)
            return
        await interaction.response.send_message(f"Selected admin action: {self.values[0]}", ephemeral=True)
        # More detailed handling can be implemented here

class WorkPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(AdminDropdown())

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You're already clocked in.", ephemeral=True)
            return
        work_data[user_id]["clocked_in"] = True
        work_data[user_id]["last_clock_in"] = datetime.utcnow()
        await interaction.response.send_message("Clocked in!", ephemeral=True)
        await log_action(f"{interaction.user.mention} clocked in.")

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if not work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You're not clocked in.", ephemeral=True)
            return
        start = work_data[user_id]["last_clock_in"]
        duration = (datetime.utcnow() - start).total_seconds()
        work_data[user_id]["total_time"] += duration
        work_data[user_id]["clocked_in"] = False
        work_data[user_id]["last_clock_in"] = None
        await interaction.response.send_message("Clocked out!", ephemeral=True)
        await log_action(f"{interaction.user.mention} clocked out.")

    async def handle_action(self, interaction, action):
        user_id = str(interaction.user.id)
        if not work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You must clock in first.", ephemeral=True)
            return
        work_data[user_id][action] += 1
        work_data[user_id]["earnings"] += PRICE_CONFIG[action]
        await interaction.response.send_message(f"{action.replace('_', ' ').title()} logged!", ephemeral=True)
        await log_action(f"{interaction.user.mention} completed {action.replace('_', ' ').title()}")
        await update_leaderboard()

    @discord.ui.button(label="Car Part", style=discord.ButtonStyle.primary, custom_id="car")
    async def upgrade_car(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car")

    @discord.ui.button(label="Bike Part", style=discord.ButtonStyle.primary, custom_id="bike")
    async def upgrade_bike(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "bike")

    @discord.ui.button(label="Engine Upgrade", style=discord.ButtonStyle.primary, custom_id="engine")
    async def engine_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "engine")

    @discord.ui.button(label="Full Car Upgrade", style=discord.ButtonStyle.secondary, custom_id="car_full")
    async def car_full_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "car_full")

    @discord.ui.button(label="Full Bike Upgrade", style=discord.ButtonStyle.secondary, custom_id="bike_full")
    async def bike_full_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "bike_full")

    @discord.ui.button(label="Repair", style=discord.ButtonStyle.secondary, custom_id="repair")
    async def repair_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_action(interaction, "repair")

async def log_action(message: str):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(message)

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
            name = user.name
        except:
            name = f"<@{user_id}>"

        clock_status = ":green_circle:" if data["clocked_in"] else ":red_circle:"
        time_str = str(timedelta(seconds=int(data["total_time"])))
        total_earned += data["earnings"]

        embed.add_field(
            name=f"{clock_status} {name}",
            value=(
                f"🚗 Car: {data['car']} | 🛵 Bike: {data['bike']}
"
                f"🛠️ Engine: {data['engine']} | 🚙 Car Full: {data['car_full']} | 🏍️ Bike Full: {data['bike_full']} | 🔧 Repair: {data['repair']}
"
                f"💳 Earnings: £{data['earnings']:,}
"
                f"⏱️ Time Clocked: {time_str} | ⚠️ Strikes: {data['strikes']}"
            ),
            inline=False
        )

    embed.set_footer(text=f"💰 Total Earned: £{total_earned:,}")

    async for msg in channel.history(limit=5):
        if msg.author == bot.user:
            await msg.delete()

    await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.add_view(WorkPanel())
    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        async for msg in panel_channel.history(limit=5):
            if msg.author == bot.user:
                await msg.delete()
        await panel_channel.send("**Work Panel**", view=WorkPanel())

bot.run(DISCORD_BOT_TOKEN)
