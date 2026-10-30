import discord
from discord.ext import commands
import io
import datetime
import html

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 
bot = commands.Bot(command_prefix="!", intents=intents)
token=""
# ================= 配置区 =================
TICKET_CATEGORY_ID =   # 你的工单分类 ID
SUPPORT_ROLE_IDS = []  # 身份组 ID
LOG_CHANNEL_ID =     # 存放聊天记录的日志频道 ID
# ==========================================
def generate_transcript(channel, messages):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Ticket Transcript - {channel.name}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #36393f; color: #dcddde; padding: 20px; }}
            h1 {{ color: #ffffff; border-bottom: 1px solid #4f545c; padding-bottom: 10px; }}
            .message {{ display: flex; margin-bottom: 15px; }}
            .avatar {{ width: 40px; height: 40px; border-radius: 50%; margin-right: 15px; }}
            .content {{ flex: 1; }}
            .header {{ margin-bottom: 5px; }}
            .author {{ font-weight: bold; color: #ffffff; margin-right: 10px; }}
            .timestamp {{ font-size: 0.8em; color: #72767d; }}
            .text {{ white-space: pre-wrap; line-height: 1.4; }}
            .attachment {{ display: block; max-width: 400px; margin-top: 10px; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <h1>Ticket Transcript: #{channel.name}</h1>
        <p>Generated on {now}</p>
        <hr>
    """
    
    for msg in reversed(messages):
        if msg.author.bot and not msg.content and not msg.attachments:
            continue
            
        avatar_url = msg.author.display_avatar.url
        author_name = html.escape(str(msg.author))
        time_str = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        content = html.escape(msg.content) if msg.content else ""
        attachments_html = ""
        for att in msg.attachments:
            if att.content_type and att.content_type.startswith("image"):
                attachments_html += f'<img class="attachment" src="{att.url}" alt="attachment">'
            else:
                attachments_html += f'<a href="{att.url}" target="_blank">📎 {html.escape(att.filename)}</a><br>'

        html_content += f"""
        <div class="message">
            <img class="avatar" src="{avatar_url}" alt="avatar">
            <div class="content">
                <div class="header">
                    <span class="author">{author_name}</span>
                    <span class="timestamp">{time_str}</span>
                </div>
                <div class="text">{content}</div>
                {attachments_html}
            </div>
        </div>
        """
        
    html_content += "</body></html>"
    return html_content
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create a ticket", style=discord.ButtonStyle.green, emoji="📩", custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        category = guild.get_channel(TICKET_CATEGORY_ID)
        for channel in category.channels:
            if f"ticket-{user.name}".lower() in channel.name.lower():
                await interaction.response.send_message(f"You have already created a ticket：{channel.mention}", ephemeral=True)
                return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        for role_id in SUPPORT_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        try:
            channel = await guild.create_text_channel(
                name=f"ticket-{user.name}",
                category=category,
                overwrites=overwrites
            )
        except Exception as e:
            await interaction.response.send_message(f"ERROR {e}", ephemeral=True)
            return

        await interaction.response.send_message(f"✅ Ticket created：{channel.mention}", ephemeral=True)
        
        embed = discord.Embed(
            title="🎫 Tickets",
            description=f"Hello {user.mention}.\n\nClick the button below to close the ticket",
            color=0x57F287
        )
        await channel.send(
            content=f"{user.mention} | " + " ".join(f"<@&{rid}>" for rid in SUPPORT_ROLE_IDS), 
            embed=embed, 
            view=CloseTicketView()
        )


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close the ticket", style=discord.ButtonStyle.red, emoji="🔒", custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_support = any(role.id in SUPPORT_ROLE_IDS for role in interaction.user.roles)
        is_owner = interaction.channel.name == f"ticket-{interaction.user.name}"
        
        if not is_support and not is_owner and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You don't have enough permission to close this ticket", ephemeral=True)
            return
            
        await interaction.response.send_message("🔒 Ticket log creating....")
        await interaction.channel.edit(name=f"closed-{interaction.channel.name}")
        messages = [msg async for msg in interaction.channel.history(limit=None)]
        transcript_html = generate_transcript(interaction.channel, messages)
        
        buf = io.BytesIO(transcript_html.encode('utf-8'))
        file = discord.File(buf, filename=f"transcript-{interaction.channel.name}.html")
        
        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="📄 Ticket closed",
                description=f"**Opened by:** {interaction.channel.name.replace('closed-ticket-', '')}\n**User:** {interaction.user.mention}\n**Channel:** {interaction.channel.name}",
                color=0xFF0000
            )
            await log_channel.send(embed=embed, file=file)
        await interaction.channel.delete(reason="Ticket closed")


@bot.event
async def on_ready():
    bot.add_view(TicketView())
    bot.add_view(CloseTicketView())
    print(f"机器人已上线: {bot.user}")

@bot.hybrid_command(name="setup_ticket", description="sending ticket panel")
@commands.has_permissions(administrator=True)
async def setup_ticket(ctx: commands.Context):
    embed = discord.Embed(
        title="🎫 Diplomatic",
        description="Use the **📩 create ticket** button.\n We will create a ticket for you.",
        color=0x57F287
    )
    await ctx.send(embed=embed, view=TicketView())
bot.run(token)
