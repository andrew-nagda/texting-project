from dotenv import load_dotenv
import os
from twilio.rest import Client

# Load environment variables from .env
load_dotenv()

# Get Twilio credentials and phone number from .env
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
from_number = os.getenv("TWILIO_FROM")

# Create Twilio client
client = Client(account_sid, auth_token)

# Replace this with your personal phone number (the one to receive the test SMS)
to_number = "+15084982017"

# Send a test message
message = client.messages.create(
    body="Lets get this party started 🚀",
    from_=from_number,
    to=to_number
)

print(f"Message sent! SID: {message.sid}")
