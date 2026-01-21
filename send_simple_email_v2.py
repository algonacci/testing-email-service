#!/usr/bin/env python3
"""
Simple Email Test Script (v2 with Config)
Uses email_config.py for recipient management
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import os
import sys

import aio_pika
from aio_pika import Message
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our email configuration
from email_config import get_simple_recipients, TEST_EMAILS

# Import crypto helper for password encryption
from crypto_helper import encrypt_smtp_password


class EmailServiceTester:
    """Simple email service tester using RabbitMQ"""

    def __init__(self):
        # Build RabbitMQ URL from environment variables
        import urllib.parse
        
        rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
        rabbitmq_port = os.getenv("RABBITMQ_PORT", "5672")
        rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
        rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "guest")
        
        # URL encode the password to handle special characters like '?' or '@'
        safe_password = urllib.parse.quote_plus(rabbitmq_password)
        
        self.rabbitmq_url = f"amqp://{rabbitmq_user}:{safe_password}@{rabbitmq_host}:{rabbitmq_port}/"
        self.queue_name = "email_queue"
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None

    async def connect(self):
        """Connect to RabbitMQ"""
        try:
            print("🔗 Connecting to RabbitMQ...")
            print(f"   Host: {os.getenv('RABBITMQ_HOST')}:{os.getenv('RABBITMQ_PORT')}")

            self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
            self.channel = await self.connection.channel()

            # Use existing queue (avoid conflicts)
            print(f"✅ Connected to RabbitMQ, queue: {self.queue_name}")

        except Exception as e:
            print(f"❌ Failed to connect to RabbitMQ: {e}")
            print(f"   URL: {self.rabbitmq_url}")
            raise

    async def close(self):
        """Close RabbitMQ connection"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            print("🔌 RabbitMQ connection closed")

    def create_email_job(
        self,
        to_emails: list[str],
        subject: str,
        body: str,
        body_html: str = "",
        smtp_config: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create email job payload following CLAUDE.md structure"""

        # SMTP configuration from environment
        smtp_password = os.getenv("SMTP_PASSWORD")

        # Encrypt SMTP password
        encrypted_password = encrypt_smtp_password(smtp_password)
        print(f"🔐 SMTP password encrypted (length: {len(encrypted_password)} chars)")

        default_smtp = {
            "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
            "port": int(os.getenv("SMTP_PORT", "587")),
            "user": os.getenv("SMTP_USER"),
            "password": encrypted_password,  # ✅ Encrypted password
            "from_name": "Email Service Test",
            "from_email": os.getenv("SMTP_USER"),  # Use same as user for Gmail
            "use_tls": True,
            "use_ssl": False,
            "timeout": 30
        }

        # Default metadata
        request_id = str(uuid.uuid4())
        default_metadata = {
            "source_app": "email-service-tester",
            "request_id": request_id,
            "queued_at": datetime.utcnow().isoformat() + "Z"
        }

        # Build email job
        email_job = {
            "email": {
                "to": to_emails,
                "subject": subject,
                "body": body,
                "priority": "normal"
            },
            "smtp": {**default_smtp, **(smtp_config or {})},
            "metadata": {**default_metadata, **(metadata or {})}
        }

        # Add HTML body if provided
        if body_html:
            email_job["email"]["body_html"] = body_html

        return email_job

    async def send_email_job(self, email_job: Dict[str, Any]) -> str:
        """Send email job to queue"""
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ")

        try:
            # Convert to JSON message
            message_body = json.dumps(email_job, indent=2)
            message = Message(
                message_body.encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT  # Persistent message
            )

            # Send to queue
            await self.channel.default_exchange.publish(
                message,
                routing_key=self.queue_name
            )

            request_id = email_job["metadata"]["request_id"]
            print(f"✅ Email job queued successfully!")
            print(f"📧 Request ID: {request_id}")
            print(f"📬 Recipients: {', '.join(email_job['email']['to'])}")
            print(f"📝 Subject: {email_job['email']['subject']}")

            return request_id

        except Exception as e:
            print(f"❌ Failed to send email job: {e}")
            raise


async def test_simple_email():
    """Test sending a simple email using config file"""
    print("🚀 Starting Simple Email Test (v2 with Config)")
    print("=" * 60)

    # Get recipients from config
    recipients = get_simple_recipients()

    print(f"📧 Email Configuration:")
    print(f"   Primary: {TEST_EMAILS['primary']}")
    print(f"   Secondary: {TEST_EMAILS['secondary']}")
    print(f"   Personal: {TEST_EMAILS['personal']}")
    print(f"   Recipients for this test: {recipients}")
    print()

    # Initialize tester
    tester = EmailServiceTester()

    try:
        # Connect to RabbitMQ
        await tester.connect()

        # Create simple email job
        print("📧 Creating simple email job...")
        email_job = tester.create_email_job(
            to_emails=recipients,
            subject="✅ Test Email from Microservice (Config Version)",
            body=f"Hello!\n\nThis is a test email from the email microservice using the config file approach.\n\nRecipient Configuration:\n- Primary: {TEST_EMAILS['primary']}\n- Secondary: {TEST_EMAILS['secondary']}\n- Personal: {TEST_EMAILS['personal']}\n\nThis email was sent via RabbitMQ queue processing.\n\nBest regards,\nEmail Service Test System",
            body_html=f"""
            <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; padding: 20px; border: 2px solid #4CAF50; border-radius: 10px;">
                <header style="text-align: center; margin-bottom: 20px;">
                    <h2 style="color: #4CAF50;">✅ Test Email from Microservice</h2>
                    <p style="color: #666;">Config Version</p>
                </header>

                <main>
                    <p>Hello!</p>
                    <p>This is a test email from the email microservice using the <strong>config file approach</strong>.</p>

                    <h3>📧 Recipient Configuration:</h3>
                    <ul>
                        <li><strong>Primary:</strong> {TEST_EMAILS['primary']}</li>
                        <li><strong>Secondary:</strong> {TEST_EMAILS['secondary']}</li>
                        <li><strong>Personal:</strong> {TEST_EMAILS['personal']}</li>
                    </ul>

                    <div style="background: #f0f8ff; padding: 15px; border-left: 4px solid #2196F3; margin: 20px 0;">
                        <p><strong>💡 Configuration Benefits:</strong></p>
                        <ul>
                            <li>Easy to update recipients in one place</li>
                            <li>Consistent across all test scripts</li>
                            <li>No need to edit multiple files</li>
                        </ul>
                    </div>

                    <p>This email was sent via RabbitMQ queue processing.</p>
                </main>

                <footer style="text-align: center; margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee;">
                    <small><em>Email Service Test System</em></small>
                </footer>
            </div>
            """
        )

        # Display email job details
        print("📋 Email Job Details:")
        print(f"   To: {email_job['email']['to']}")
        print(f"   Subject: {email_job['email']['subject']}")
        print(f"   SMTP Host: {email_job['smtp']['host']}")
        print(f"   Source App: {email_job['metadata']['source_app']}")
        print()

        # Send email job
        print("📤 Sending email job to queue...")
        request_id = await tester.send_email_job(email_job)

        print()
        print("✅ Test completed!")
        print(f"📍 Request ID: {request_id}")
        print("🔍 Database query:")
        print("   SELECT * FROM email_jobs WHERE source_service = 'email-service-tester'")

    except Exception as e:
        print(f"💥 Test failed: {e}")
        print()
        print("🔧 Check .env settings and email_config.py")
        sys.exit(1)

    finally:
        # Clean up connection
        await tester.close()


def print_usage():
    """Print usage instructions"""
    print("📧 Simple Email Test Script (v2 with Config)")
    print("=" * 50)
    print()
    print("This script sends a simple test email using email_config.py for recipients.")
    print()
    print("🔧 Setup Steps:")
    print("   1. Edit email_config.py and update TEST_EMAILS with your real emails")
    print("   2. Ensure .env has correct RabbitMQ and SMTP settings")
    print("   3. Run this script")
    print()
    print("📧 Current Configuration:")
    print(f"   Primary: {TEST_EMAILS['primary']}")
    print(f"   Secondary: {TEST_EMAILS['secondary']}")
    print(f"   Personal: {TEST_EMAILS['personal']}")
    print()
    print("🚀 Usage:")
    print("   python send_simple_email_v2.py")
    print()


if __name__ == "__main__":
    # Check for help flag
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help", "help"]:
        print_usage()
        sys.exit(0)

    # Run the test
    print("🧪 Email Service - Simple Email Test (v2)")
    print("🕐", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print()

    # Check if emails are still default
    if "your-email@gmail.com" in [TEST_EMAILS['primary'], TEST_EMAILS['secondary'], TEST_EMAILS['personal']]:
        print("⚠️  WARNING: Using default email addresses!")
        print("   Please edit email_config.py and update TEST_EMAILS with your actual email addresses")
        print("   Current settings:")
        print(f"     Primary: {TEST_EMAILS['primary']}")
        print(f"     Secondary: {TEST_EMAILS['secondary']}")
        print(f"     Personal: {TEST_EMAILS['personal']}")
        print()

        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Setup email_config.py first, then run the test again.")
            sys.exit(0)

    # Run async test
    asyncio.run(test_simple_email())