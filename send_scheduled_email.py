#!/usr/bin/env python3
"""
Scheduled Email Test Script
Tests email scheduling functionality for future delivery
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import os
import sys

import aio_pika
from aio_pika import Message
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import crypto helper for password encryption
from crypto_helper import encrypt_smtp_password


class ScheduledEmailTester:
    """Email service tester for scheduled email delivery"""

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

    def create_scheduled_email(
        self,
        to_emails: list[str],
        subject: str,
        body: str,
        body_html: str = "",
        scheduled_at: datetime = None,
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """Create scheduled email job"""

        # SMTP configuration from environment
        smtp_password = os.getenv("SMTP_PASSWORD")

        # Encrypt SMTP password
        encrypted_password = encrypt_smtp_password(smtp_password)
        print(f"🔐 SMTP password encrypted")

        smtp_config = {
            "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
            "port": int(os.getenv("SMTP_PORT", "587")),
            "user": os.getenv("SMTP_USER"),
            "password": encrypted_password,  # ✅ Encrypted password
            "from_name": "Scheduled Email Test",
            "from_email": os.getenv("SMTP_USER"),  # Use same as user for Gmail
            "use_tls": True,
            "use_ssl": False,
            "timeout": 30
        }

        # Request tracking
        request_id = f"scheduled_{uuid.uuid4().hex[:8]}"
        metadata = {
            "source_app": "scheduled-email-tester",
            "request_id": request_id,
            "queued_at": datetime.utcnow().isoformat() + "Z"
        }

        # Add scheduled_at if provided
        if scheduled_at:
            metadata["scheduled_at"] = scheduled_at.isoformat() + "Z"

        # Build email job
        email_job = {
            "email": {
                "to": to_emails,
                "subject": subject,
                "body": body,
                "priority": priority
            },
            "smtp": smtp_config,
            "metadata": metadata
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
            message_body = json.dumps(email_job, indent=2)
            message = Message(
                message_body.encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )

            await self.channel.default_exchange.publish(message, routing_key=self.queue_name)

            request_id = email_job["metadata"]["request_id"]
            scheduled_at = email_job["metadata"].get("scheduled_at")

            print(f"✅ Scheduled email queued!")
            print(f"📧 Request ID: {request_id}")
            print(f"📬 Recipients: {', '.join(email_job['email']['to'])}")
            print(f"📝 Subject: {email_job['email']['subject']}")

            if scheduled_at:
                scheduled_time = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                print(f"⏰ Scheduled for: {scheduled_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

                # Calculate time until delivery
                now = datetime.utcnow()
                time_diff = scheduled_time.replace(tzinfo=None) - now
                if time_diff.total_seconds() > 0:
                    print(f"⏳ Time until delivery: {format_time_delta(time_diff)}")
                else:
                    print("⚡ Scheduled time is in the past - will be sent immediately")
            else:
                print("🚀 No scheduling - will be sent immediately")

            return request_id

        except Exception as e:
            print(f"❌ Failed to send email job: {e}")
            raise


def format_time_delta(td: timedelta) -> str:
    """Format timedelta as human readable string"""
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


async def test_scheduled_emails():
    """Test various scheduled email scenarios"""
    print("🚀 Starting Scheduled Email Tests")
    print("=" * 50)

    tester = ScheduledEmailTester()

    try:
        await tester.connect()

        # Test Case 1: Email scheduled 30 seconds from now
        print("\n📧 Test Case 1: 30-Second Delayed Email")
        print("-" * 40)

        scheduled_time_1 = datetime.utcnow() + timedelta(seconds=30)

        email_job1 = tester.create_scheduled_email(
            to_emails=[os.getenv("TEST_EMAIL")],
            subject="⏰ 30-Second Scheduled Email Test",
            body=f"Hello!\n\nThis email was scheduled to be sent at {scheduled_time_1.strftime('%Y-%m-%d %H:%M:%S UTC')}.\n\nIf you're reading this, the scheduling system is working correctly!\n\nScheduled Email Test System",
            body_html=f"""
            <div style="padding: 20px; border-left: 4px solid #2196F3;">
                <h2>⏰ Scheduled Email Test</h2>
                <p>Hello!</p>
                <p>This email was scheduled to be sent at:</p>
                <p style="background: #f0f8ff; padding: 10px; font-weight: bold; text-align: center;">
                    📅 {scheduled_time_1.strftime('%Y-%m-%d %H:%M:%S UTC')}
                </p>
                <p>If you're reading this, the scheduling system is working correctly!</p>
                <hr>
                <small><em>Scheduled Email Test System</em></small>
            </div>
            """,
            scheduled_at=scheduled_time_1,
            priority="normal"
        )

        request_id1 = await tester.send_email_job(email_job1)
        await asyncio.sleep(1)

        # Test Case 2: Email scheduled 1 minute from now
        print("\n📧 Test Case 2: 1-Minute Delayed Email")
        print("-" * 40)

        scheduled_time_2 = datetime.utcnow() + timedelta(minutes=1)

        email_job2 = tester.create_scheduled_email(
            to_emails=[os.getenv("TEST_EMAIL")],
            subject="📅 1-Minute Report - Scheduled Delivery Test",
            body=f"Hourly Report\n\nReport scheduled for: {scheduled_time_2.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n--- REPORT CONTENTS ---\n\n• Scheduled emails: Testing in progress\n• Delivery system: Operational\n• Queue processing: Active\n• Database logging: Enabled\n\nThis is an automated test of the scheduled email system.\n\nReport Generation System",
            body_html=f"""
            <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif;">
                <header style="background: #FF9800; color: white; padding: 20px; text-align: center;">
                    <h1>📅 Hourly Report</h1>
                    <p>Scheduled Delivery Test</p>
                </header>

                <main style="padding: 20px;">
                    <p><strong>Report scheduled for:</strong></p>
                    <div style="background: #fff3e0; padding: 15px; border-radius: 5px; margin: 15px 0;">
                        <h3 style="margin: 0;">📅 {scheduled_time_2.strftime('%Y-%m-%d %H:%M:%S UTC')}</h3>
                    </div>

                    <h3>📊 Report Contents</h3>
                    <ul>
                        <li>✅ Scheduled emails: Testing in progress</li>
                        <li>✅ Delivery system: Operational</li>
                        <li>✅ Queue processing: Active</li>
                        <li>✅ Database logging: Enabled</li>
                    </ul>

                    <p><em>This is an automated test of the scheduled email system.</em></p>
                </main>

                <footer style="background: #f5f5f5; padding: 15px; text-align: center; font-size: 12px;">
                    <p><strong>Report Generation System</strong></p>
                </footer>
            </div>
            """,
            scheduled_at=scheduled_time_2,
            priority="normal"
        )

        request_id2 = await tester.send_email_job(email_job2)
        await asyncio.sleep(1)

        # Test Case 3: Email scheduled 3 minutes from now
        print("\n📧 Test Case 3: 3-Minute Delayed Email")
        print("-" * 40)

        scheduled_time_3 = datetime.utcnow() + timedelta(minutes=3)

        email_job3 = tester.create_scheduled_email(
            to_emails=[os.getenv("TEST_EMAIL")],
            subject="⏰ 3-Minute Delayed Test",
            body=f"Hello!\n\nThis is a 3-minute delayed email test.\n\nScheduled for: {scheduled_time_3.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\nThis demonstrates medium delay scheduling and queue management.\n\nScheduled Email System",
            body_html=f"""
            <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
                <header style="padding: 30px; text-align: center;">
                    <h1>🌅 Good Morning!</h1>
                    <h2>Daily Scheduled Report</h2>
                    <p>{scheduled_time_3.strftime('%A, %B %d, %Y')}</p>
                </header>

                <main style="background: white; color: #333; padding: 30px; margin: 20px;">
                    <h3>📋 Daily Summary</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Email scheduling:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">✅ Working</td></tr>
                        <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Queue processing:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">✅ Operational</td></tr>
                        <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Database tracking:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">✅ Active</td></tr>
                        <tr><td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>SMTP delivery:</strong></td><td style="padding: 10px; border-bottom: 1px solid #eee;">✅ Configured</td></tr>
                    </table>

                    <div style="background: #e8f5e8; padding: 20px; margin: 20px 0; border-radius: 5px; text-align: center;">
                        <p><strong>📅 Scheduled delivery time:</strong></p>
                        <h3 style="margin: 5px 0;">{scheduled_time_3.strftime('%Y-%m-%d %H:%M:%S UTC')}</h3>
                    </div>

                    <p style="text-align: center; font-size: 18px;"><strong>Have a great day! ☀️</strong></p>
                </main>

                <footer style="padding: 20px; text-align: center; font-size: 12px;">
                    <p><em>Daily Report System</em></p>
                </footer>
            </div>
            """,
            scheduled_at=scheduled_time_3,
            priority="low"  # Lower priority for daily reports
        )

        request_id3 = await tester.send_email_job(email_job3)

        # Test Case 4: Immediate email (no scheduling) for comparison
        print("\n📧 Test Case 4: Immediate Email (No Scheduling)")
        print("-" * 40)

        email_job4 = tester.create_scheduled_email(
            to_emails=[os.getenv("TEST_EMAIL")],
            subject="🚀 Immediate Email - No Scheduling Test",
            body="Hello!\n\nThis email has no scheduling and should be sent immediately.\n\nThis serves as a comparison to the scheduled emails above.\n\nImmediate Delivery Test System",
            body_html="""
            <div style="padding: 20px; border-left: 4px solid #4CAF50;">
                <h2>🚀 Immediate Email</h2>
                <p>Hello!</p>
                <p>This email has <strong>no scheduling</strong> and should be sent immediately.</p>
                <p>This serves as a comparison to the scheduled emails above.</p>
                <hr>
                <small><em>Immediate Delivery Test System</em></small>
            </div>
            """,
            scheduled_at=None,  # No scheduling
            priority="high"
        )

        request_id4 = await tester.send_email_job(email_job4)

        # Test summary
        print("\n" + "=" * 50)
        print("🎉 All Scheduled Email Tests Completed!")
        print("=" * 50)

        print("\n📊 Test Summary:")
        print(f"   📧 {request_id1}: 30-second delay")
        print(f"   📧 {request_id2}: 1-minute delay")
        print(f"   📧 {request_id3}: 3-minute delay")
        print(f"   📧 {request_id4}: Immediate (no schedule)")

        current_time = datetime.utcnow()
        print(f"\n⏰ Current UTC time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("\n🔍 Database query:")
        print("   SELECT * FROM email_jobs WHERE source_service = 'scheduled-email-tester'")

    except Exception as e:
        print(f"💥 Test failed: {e}")
        sys.exit(1)

    finally:
        await tester.close()


def print_usage():
    """Print usage instructions"""
    print("📧 Scheduled Email Test Script")
    print("=" * 35)
    print()
    print("Tests email scheduling functionality:")
    print("   • 30-second delayed delivery")
    print("   • 1-minute delayed delivery")
    print("   • 3-minute delayed delivery")
    print("   • Immediate delivery comparison")
    print()
    print("🔧 Required .env variables:")
    print("   RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASSWORD")
    print("   SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD")
    print()
    print("🚀 Usage:")
    print("   python send_scheduled_email.py")
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help", "help"]:
        print_usage()
        sys.exit(0)

    print("🧪 Email Service - Scheduled Email Test")
    print("🕐", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print()

    # Verify required environment variables
    required_vars = ["RABBITMQ_HOST", "SMTP_USER", "SMTP_PASSWORD"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("   Please check your .env file")
        sys.exit(1)

    asyncio.run(test_scheduled_emails())