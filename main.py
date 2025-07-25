import discord
from discord.ext import commands, tasks
import os
from datetime import datetime, timedelta
from collections import defaultdict

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))

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

PRICE_CONFIG = {
    "car": 50000,
    "bike": 50000,
    "engine": 500000,
    "car_full": 850000,
    "bike_full": 300000,
    "repair": 25000
}

class WorkPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(AdminDropdown())

    async def handle_action(self, interaction, action):
        user_id = str(interaction.user.id)
        if not work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You must clock in first!", ephemeral=True)
            return
        work_data[user_id][action] += 1
        work_data[user_id]["earnings"] += PRICE_CONFIG[action]
        await interaction.response.send_message(f"{action.replace('_', ' ').title()} recorded!", ephemeral=True)
        await log_action(f"{interaction.user.mention} completed **{action.replace('_', ' ').title()}**.")
        await update_leaderboard()

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You're already clocked in!", ephemeral=True)
            return
        work_data[user_id]["clocked_in"] = True
        work_data[user_id]["last_clock_in"] = datetime.utcnow()
        await interaction.response.send_message("You are now clocked in.", ephemeral=True)
        await log_action(f"{interaction.user.mention} clocked in.")
        await update_leaderboard()

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if not work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You aren't clocked in.", ephemeral=True)
            return
        start = work_data[user_id]["last_clock_in"]
        duration = (datetime.utcnow() - start).total_seconds()
        work_data[user_id]["total_time"] += duration
        work_data[user_id]["clocked_in"] = False
        work_data[user_id]["last_clock_in"] = None
        await interaction.response.send_message("You are now clocked out.", ephemeral=True)
        await log_action(f"{interaction.user.mention} clocked out.")
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
            discord.SelectOption(label="Force Clock Out", value="force_clock_out"),
            discord.SelectOption(label="Remove Car Part", value="remove_car"),
            discord.SelectOption(label="Remove Bike Part", value="remove_bike"),
            discord.SelectOption(label="Remove Engine Upgrade", value="remove_engine"),
            discord.SelectOption(label="Remove Full Car Upgrade", value="remove_car_full"),
            discord.SelectOption(label="Remove Full Bike Upgrade", value="remove_bike_full"),
            discord.SelectOption(label="Remove Repair", value="remove_repair"),
            discord.SelectOption(label="Remove Time", value="remove_time")
        ]
        super().__init__(placeholder="Admin Options", min_values=1, max_values=1, options=options, custom_id="admin_dropdown")

    async def callback(self, interaction: discord.Interaction):
        if ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("You don't have permission.", ephemeral=True)
            return

        view = UserSelectView(action=self.values[0])
        await interaction.response.send_message("Select a user to apply the action:", view=view, ephemeral=True)

class UserSelectView(discord.ui.View):
    def __init__(self, action):
        super().__init__(timeout=60)
        self.add_item(UserDropdown(action))

class UserDropdown(discord.ui.UserSelect):
    def __init__(self, action):
        super().__init__(placeholder="Select a user", min_values=1, max_values=1)
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        user = self.values[0]
        user_id = str(user.id)

        if self.action == "force_clock_out":
            if work_data[user_id]["clocked_in"]:
                work_data[user_id]["clocked_in"] = False
                work_data[user_id]["last_clock_in"] = None
                await log_action(f"🔴 {user.mention} was force-clocked out by {interaction.user.mention}")
        elif self.action.startswith("remove_"):
            key = self.action.replace("remove_", "")
            if key == "time":
                work_data[user_id]["total_time"] = max(0, work_data[user_id]["total_time"] - 3600)
                await log_action(f"⏱️ 1 hour removed from {user.mention} by {interaction.user.mention}")
            else:
                if work_data[user_id][key] > 0:
                    work_data[user_id][key] -= 1
                    work_data[user_id]["earnings"] -= PRICE_CONFIG[key]
                    await log_action(f"🧾 {key.replace('_', ' ').title()} removed from {user.mention} by {interaction.user.mention}")

        await interaction.response.send_message(f"✅ Action completed for {user.display_name}.", ephemeral=True)
        await update_leaderboard()

async def log_action(msg):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(msg)

async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return

    leaderboard = sorted(work_data.items(), key=lambda x: x[1]["earnings"], reverse=True)
    embed = discord.Embed(title="🏆 Work Leaderboard", color=discord.Color.gold())

    total_earnings = 0
    for user_id, data in leaderboard:
        try:
            user = await bot.fetch_user(int(user_id))
            name = user.name
        except:
            name = f"<@{user_id}>"

        status = ":green_circle:" if data["clocked_in"] else ":red_circle:"
        total_earnings += data["earnings"]

        embed.add_field(
            name=f"{status} {name}",
            value=(
                f"🚗 Car: {data['car']} | 🛵 Bike: {data['bike']} | 🔧 Repair: {data['repair']}\n"
                f"🛠️ Engine: {data['engine']} | 🚙 Car Full: {data['car_full']} | 🏍️ Bike Full: {data['bike_full']}\n"
                f"💷 Earnings: £{data['earnings']:,}\n"
                f"⏱️ Time: {str(timedelta(seconds=int(data['total_time'])))} | ⚠️ Strikes: {data['strikes']}"
            ),
            inline=False
        )

    embed.set_footer(text=f"💰 Total Earnings: £{total_earnings:,}")

    async for msg in channel.history(limit=5):
        if msg.author == bot.user:
            await msg.delete()
    await channel.send(embed=embed)

@tasks.loop(minutes=10)
async def check_clocked_in_users():
    now = datetime.utcnow()
    for user_id, data in list(work_data.items()):
        if data["clocked_in"] and data["last_clock_in"]:
            clocked_duration = (now - data["last_clock_in"]).total_seconds()
            if clocked_duration >= 10800:  # 3 hours
                user = await bot.fetch_user(int(user_id))
                try:
                    await user.send("⚠️ You've been clocked in for 3 hours. Please reply to stay clocked in.")
                except:
                    continue

                def check(m): return m.author.id == int(user_id) and m.channel.type == discord.ChannelType.private
                try:
                    await bot.wait_for("message", timeout=1800, check=check)  # 30 mins
                except:
                    data["clocked_in"] = False
                    data["last_clock_in"] = None
                    data["total_time"] = max(0, data["total_time"] - 32400)  # Remove 9 hours
                    data["strikes"] += 1

                    log_channel = bot.get_channel(LOG_CHANNEL_ID)
                    if log_channel:
                        await log_channel.send(f"🚨 {user.mention} auto-clocked out. -9h. Strike {data['strikes']}/3. <@&{ADMIN_ROLE_ID}>")

                    try:
                        await user.send(f"⚠️ You were auto-clocked out. 9h removed. You now have {data['strikes']} strike(s).")
                    except:
                        pass

                    if data["strikes"] >= 3:
                        del work_data[user_id]
                        await log_channel.send(f"❌ {user.mention}'s data wiped after 3 strikes. <@&{ADMIN_ROLE_ID}>")
                        try:
                            await user.send("❌ Your data has been wiped after 3 strikes. Management has been notified.")
                        except:
                            pass
    await update_leaderboard()

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    bot.add_view(WorkPanel())

    panel_channel = bot.get_channel(PANEL_CHANNEL_ID)
    if panel_channel:
        async for msg in panel_channel.history(limit=5):
            if msg.author == bot.user:
                await msg.delete()
        await panel_channel.send("**Work Tracker Panel**", view=WorkPanel())

    check_clocked_in_users.start()

bot.run(DISCORD_BOT_TOKEN)
