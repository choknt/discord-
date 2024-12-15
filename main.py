from flask import Flask, redirect, request, session
from dotenv import load_dotenv
import os
import threading
import requests
import discord
from discord.ext import commands
from playfab.PlayFabClientApi import PlayFabClientAPI

# โหลดตัวแปรจากไฟล์ .env
load_dotenv()

# ตั้งค่าคีย์ลับ
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
DISCORD_API_BASE_URL = "https://discord.com/api"
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID"))
LOGIN_CHANNEL_ID = int(os.getenv("DISCORD_LOGIN_CHANNEL_ID"))
LOGIN_ROLE_ID = int(os.getenv("DISCORD_LOGIN_ROLE_ID"))
PLAYFAB_TITLE_ID = os.getenv("PLAYFAB_TITLE_ID")
SECRET_KEY = os.getenv("SECRET_KEY")

# Flask App
app = Flask(__name__)
app.secret_key = SECRET_KEY

# Discord Bot
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# PlayFab Client
playfab_client = PlayFabClientAPI(title_id=PLAYFAB_TITLE_ID)

@app.route("/")
def home():
    return "<h1>Welcome to the Login System</h1>"

@app.route("/login")
def login():
    discord_auth_url = (
        f"{DISCORD_API_BASE_URL}/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify"
    )
    return redirect(discord_auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Error: No authorization code provided"

    # ขอ Access Token จาก Discord
    token_url = f"{DISCORD_API_BASE_URL}/oauth2/token"
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_response = requests.post(token_url, data=data, headers=headers)
    if token_response.status_code != 200:
        return f"Error fetching token: {token_response.text}"

    token = token_response.json().get("access_token")

    # ดึงข้อมูลผู้ใช้จาก Discord
    user_response = requests.get(
        f"{DISCORD_API_BASE_URL}/users/@me", headers={"Authorization": f"Bearer {token}"}
    )
    if user_response.status_code != 200:
        return f"Error fetching user data: {user_response.text}"

    user_data = user_response.json()
    discord_user_id = user_data.get("id")
    discord_username = user_data.get("username")

    # ล็อกอินหรือสร้างบัญชีใน PlayFab
    playfab_request = {"CustomId": discord_user_id, "CreateAccount": True}
    try:
        playfab_response = playfab_client.LoginWithCustomID(playfab_request)
        session_ticket = playfab_response["data"]["SessionTicket"]

        # เพิ่มบทบาท @login ใน Discord
        notify_bot_to_add_role(discord_user_id)

        return f"Welcome, {discord_username}! You are now logged in and have been assigned the @login role."
    except Exception as e:
        return f"Error with PlayFab login: {str(e)}"

def notify_bot_to_add_role(discord_user_id):
    guild = bot.get_guild(GUILD_ID)
    member = guild.get_member(int(discord_user_id))
    if member:
        role = discord.utils.get(guild.roles, id=LOGIN_ROLE_ID)
        if role:
            bot.loop.create_task(member.add_roles(role))

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")

# สร้างปุ่มในห้อง #login
@bot.event
async def on_message(message):
    if message.channel.id == LOGIN_CHANNEL_ID and message.content.lower() == "!login":
        await message.channel.send(
            "Click the button below to log in!",
            view=discord.ui.View(
                discord.ui.Button(
                    label="Log in with Discord",
                    url=f"https://yourdomain.com/login"
                )
            )
        )

# รัน Flask และ Discord Bot พร้อมกัน
def run_flask():
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run(DISCORD_TOKEN)
