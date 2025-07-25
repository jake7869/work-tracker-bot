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

PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL_ID"))
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_ROLE_ID = 1391785348262264925

PRICES = {
    "Car Part": 20000,
    "Bike Part": 20000,
    "Car Full Upgrade": 500000,
    "Bike Full Upgrade": 250000,
    "Engine Upgrade": 250000
}

class WorkPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(AdminActions())

    @discord.ui.button(label="Clock In", style=discord.ButtonStyle.success, custom_id="clock_in")
    async def clock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You are already clocked in.", ephemeral=True)
        else:
            work_data[user_id]["clocked_in"] = True
            work_data[user_id]["last_clock_in"] = datetime.utcnow()
            await interaction.response.send_message("You clocked in!", ephemeral=True)
            await log_action(f"{interaction.user.mention} clocked in.")
            await update_leaderboard()

    @discord.ui.button(label="Clock Out", style=discord.ButtonStyle.danger, custom_id="clock_out")
    async def clock_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if not work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You are not clocked in.", ephemeral=True)
        else:
            start = work_data[user_id]["last_clock_in"]
            duration = (datetime.utcnow() - start).total_seconds()
            work_data[user_id]["total_time"] += duration
            work_data[user_id]["clocked_in"] = False
            work_data[user_id]["last_clock_in"] = None
            await interaction.response.send_message("You clocked out!", ephemeral=True)
            await log_action(f"{interaction.user.mention} clocked out. Session: {round(duration/3600, 2)} hours")
            await update_leaderboard()

    async def handle_action(self, interaction, action):
        user_id = str(interaction.user.id)
        if not work_data[user_id]["clocked_in"]:
            await interaction.response.send_message("You must clock in first.", ephemeral=True)
            return
        work_data[user_id][action] += 1
        work_data[user_id]["earnings"] += PRICE_CONFIG[action]
        await interaction.response.send_message(f"{action.replace('_',' ').title()} recorded!", ephemeral=True)
        await log_action(f"{interaction.user.mention} completed **{action.replace('_',' ').title()}**.")
        await update_leaderboard()

    @discord.ui.button(label="Car Part", style=discord.ButtonStyle.primary, custom_id="car")
    async def car_part(self, interaction, button): await self.handle_action(interaction, "car")

    @discord.ui.button(label="Bike Part", style=discord.ButtonStyle.primary, custom_id="bike")
    async def bike_part(self, interaction, button): await self.handle_action(interaction, "bike")

    @discord.ui.button(label="Engine Upgrade", style=discord.ButtonStyle.primary, custom_id="engine")
    async def engine_upgrade(self, interaction, button): await self.handle_action(interaction, "engine")

    @discord.ui.button(label="Full Car Upgrade", style=discord.ButtonStyle.secondary, custom_id="car_full")
    async def full_car(self, interaction, button): await self.handle_action(interaction, "car_full")

    @discord.ui.button(label="Full Bike Upgrade", style=discord.ButtonStyle.secondary, custom_id="bike_full")
    async def full_bike(self, interaction, button): await self.handle_action(interaction, "bike_full")

    @discord.ui.button(label="Repair", style=discord.ButtonStyle.secondary, custom_id="repair")
    async def repair(self, interaction, button): await self.handle_action(interaction, "repair")

    @discord.ui.button(label="Refresh Leaderboard", style=discord.ButtonStyle.success, custom_id="refresh")
    async def refresh(self, interaction, button):
        if ADMIN_ROLE_ID in [r.id for r in interaction.user.roles]:
            await update_leaderboard()
            await interaction.response.send_message("Leaderboard refreshed.", ephemeral=True)
        else:
            await interaction.response.send_message("Admin only.", ephemeral=True)

    @discord.ui.button(label="Reset Leaderboard", style=discord.ButtonStyle.danger, custom_id="reset")
    async def reset(self, interaction, button):
        if ADMIN_ROLE_ID in [r.id for r in interaction.user.roles]:
            view = ConfirmResetView()
            await interaction.response.send_message("Confirm leaderboard reset:", view=view, ephemeral=True)
        else:
            await interaction.response.send_message("Admin only.", ephemeral=True)

class ConfirmResetView(discord.ui.View):
    @discord.ui.button(label="Confirm Reset", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button):
        work_data.clear()
        await update_leaderboard()
        await interaction.response.edit_message(content="Leaderboard reset.", view=None)
        await log_action(f"{interaction.user.mention} reset the leaderboard.")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, button):
        await interaction.response.edit_message(content="Reset cancelled.", view=None)

class AdminActions(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Force Clock Out", value="force_clock"),
            discord.SelectOption(label="Remove Car Part", value="car"),
            discord.SelectOption(label="Remove Bike Part", value="bike"),
            discord.SelectOption(label="Remove Engine Upgrade", value="engine"),
            discord.SelectOption(label="Remove Full Car Upgrade", value="car_full"),
            discord.SelectOption(label="Remove Full Bike Upgrade", value="bike_full"),
            discord.SelectOption(label="Remove Repair", value="repair"),
            discord.SelectOption(label="Remove Time (1hr)", value="remove_time")
        ]
        super().__init__(placeholder="Admin Tools", options=options, custom_id="admin_tools")

    async def callback(self, interaction):
        if ADMIN_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("Admin only.", ephemeral=True)
            return

        members = [m async for m in interaction.guild.fetch_members(limit=None)]
        view = AdminUserSelect(self.values[0], members)
        await interaction.response.send_message("Select user:", view=view, ephemeral=True)

class AdminUserSelect(discord.ui.View):
    def __init__(self, action, members):
        super().__init__(timeout=30)
        self.add_item(AdminMemberDropdown(action, members))

class AdminMemberDropdown(discord.ui.Select):
    def __init__(self, action, members):
        self.action = action
        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id))
            for m in members if not m.bot
        ][:25]
        super().__init__(placeholder="Select a user", options=options)

    async def callback(self, interaction):
        user_id = self.values[0]
        if self.action == "force_clock":
            work_data[user_id]["clocked_in"] = False
            work_data[user_id]["last_clock_in"] = None
            await interaction.response.send_message("User clocked out.", ephemeral=True)
            await log_action(f"{interaction.user.mention} force clocked out <@{user_id}>.")
        elif self.action == "remove_time":
            work_data[user_id]["total_time"] = max(0, work_data[user_id]["total_time"] - 3600)
            await interaction.response.send_message("1 hour removed.", ephemeral=True)
            await log_action(f"{interaction.user.mention} removed 1 hour from <@{user_id}>.")
        else:
            work_data[user_id][self.action] = max(0, work_data[user_id][self.action] - 1)
            work_data[user_id]["earnings"] -= PRICE_CONFIG[self.action]
            await interaction.response.send_message(f"{self.action.replace('_',' ').title()} removed.", ephemeral=True)
            await log_action(f"{interaction.user.mention} removed {self.action} from <@{user_id}>.")
        await update_leaderboard()

async def log_action(msg):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(msg)

async def update_leaderboard():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel: return
    await channel.purge(limit=10, check=lambda m: m.author == bot.user)

    leaderboard = sorted(work_data.items(), key=lambda x: x[1]["earnings"], reverse=True)
    embed = discord.Embed(title="🏆 Work Leaderboard", color=discord.Color.gold())

    total_earnings = 0
    for user_id, data in leaderboard:
        try:
            user = await bot.fetch_user(int(user_id))
            status_icon = "🟢" if data["clocked_in"] else "🔴"
            name = f"{status_icon} {user.name}"
        except:
            name = f"<@{user_id}>"

        total_earnings += data["earnings"]
        time_str = str(timedelta(seconds=int(data["total_time"])))
        embed.add_field(
            name=name,
            value=(f"🚗 {data['car']} 🛵 {data['bike']} 🛠️ {data['engine']} 🚙 {data['car_full']} 🏍️ {data['bike_full']} 🧰 {data['repair']}\n"
                   f"💳 £{data['earnings']:,} | ⏱️ {time_str}"),
            inline=False
        )

    embed.set_footer(text=f"💰 Total Earned: £{total_earnings:,}")
    await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.add_view(WorkPanel())
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if channel:
        await channel.purge(limit=5, check=lambda m: m.author == bot.user)
        await channel.send("**Work Panel**", view=WorkPanel())
    check_clocked_in_users.start()

@tasks.loop(minutes=10)
async def check_clocked_in_users():
    now = datetime.utcnow()
    for user_id, data in list(work_data.items()):
        if data["clocked_in"] and data["last_clock_in"]:
            duration = (now - data["last_clock_in"]).total_seconds()
            if duration >= 10800:  # 3 hours
                user = await bot.fetch_user(int(user_id))
                try:
                    await user.send("⚠️ You've been clocked in for 3 hours. Reply within 30 minutes to stay clocked in.")
                    await wait_for_dm_response(user, user_id)
                except:
                    pass

async def wait_for_dm_response(user, user_id):
    def check(m): return m.author.id == user.id and isinstance(m.channel, discord.DMChannel)
    try:
        msg = await bot.wait_for("message", check=check, timeout=1800)
    except:
        # No reply, penalize
        work_data[user_id]["clocked_in"] = False
        work_data[user_id]["last_clock_in"] = None
        work_data[user_id]["total_time"] = max(0, work_data[user_id]["total_time"] - 9 * 3600)
        work_data[user_id]["strikes"] += 1
        if work_data[user_id]["strikes"] >= 3:
            del work_data[user_id]
            await log_action(f"<@{user_id}> reached 3 strikes. Data wiped. <@&{ADMIN_ROLE_ID}>")
            try: await user.send("⚠️ You reached 3 strikes. Your data was wiped and staff were informed.")
            except: pass
        else:
            await log_action(f"<@{user_id}> auto clocked out and penalized. Strike {work_data[user_id]['strikes']}/3. <@&{ADMIN_ROLE_ID}>")
            try: await user.send(f"⚠️ You were auto clocked out and 9 hours removed. You now have {work_data[user_id]['strikes']} strike(s).")
            except: pass
        await update_leaderboard()

bot.run(DISCORD_BOT_TOKEN)
