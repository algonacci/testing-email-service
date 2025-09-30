#!/usr/bin/env python3
"""
Bulk Email Test Script
Tests sending multiple email jobs rapidly to simulate bulk email functionality
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import os
import sys

import aio_pika
from aio_pika import Message
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import crypto helper for password encryption
from crypto_helper import encrypt_smtp_password


class BulkEmailTester:
    """Email service tester for bulk email sending"""

    def __init__(self):
        # Build RabbitMQ URL from environment variables
        rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
        rabbitmq_port = os.getenv("RABBITMQ_PORT", "5672")
        rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
        rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "guest")

        self.rabbitmq_url = f"amqp://{rabbitmq_user}:{rabbitmq_password}@{rabbitmq_host}:{rabbitmq_port}/"
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
            raise

    async def close(self):
        """Close RabbitMQ connection"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            print("🔌 RabbitMQ connection closed")

    def create_email_job(
        self,
        to_email: str,
        subject: str,
        body: str,
        body_html: str = "",
        priority: str = "normal",
        custom_headers: Dict[str, str] = None,
        bulk_id: str = None,
        job_index: int = None
    ) -> Dict[str, Any]:
        """Create individual email job for bulk sending"""

        # SMTP configuration from environment
        smtp_password = os.getenv("SMTP_PASSWORD")

        # Encrypt SMTP password
        encrypted_password = encrypt_smtp_password(smtp_password)

        smtp_config = {
            "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
            "port": int(os.getenv("SMTP_PORT", "587")),
            "user": os.getenv("SMTP_USER"),
            "password": encrypted_password,  # ✅ Encrypted password
            "from_name": "Bulk Email Test",
            "from_email": os.getenv("SMTP_USER"),
            "use_tls": True,
            "use_ssl": False,
            "timeout": 30
        }

        # Request tracking
        request_id = f"bulk_{bulk_id}_{job_index:03d}" if bulk_id and job_index is not None else f"bulk_{uuid.uuid4().hex[:8]}"
        metadata = {
            "source_app": "bulk-email-tester",
            "request_id": request_id,
            "queued_at": datetime.utcnow().isoformat() + "Z"
        }

        # Add bulk tracking info
        if bulk_id:
            metadata["bulk_id"] = bulk_id
        if job_index is not None:
            metadata["bulk_index"] = job_index

        # Build email job
        email_data = {
            "to": [to_email],
            "subject": subject,
            "body": body,
            "priority": priority
        }

        # Add HTML body if provided
        if body_html:
            email_data["body_html"] = body_html

        # Add custom headers if provided
        if custom_headers:
            email_data["headers"] = custom_headers

        email_job = {
            "email": email_data,
            "smtp": smtp_config,
            "metadata": metadata
        }

        return email_job

    async def send_email_job(self, email_job: Dict[str, Any], show_details: bool = True) -> str:
        """Send email job to queue"""
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ")

        try:
            message_body = json.dumps(email_job)
            message = Message(
                message_body.encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )

            await self.channel.default_exchange.publish(message, routing_key=self.queue_name)

            request_id = email_job["metadata"]["request_id"]

            if show_details:
                print(f"✅ Bulk email queued: {request_id}")
                print(f"   📧 To: {email_job['email']['to'][0]}")
                print(f"   📝 Subject: {email_job['email']['subject']}")

            return request_id

        except Exception as e:
            print(f"❌ Failed to send email job: {e}")
            raise

    async def send_bulk_emails(
        self,
        email_templates: List[Dict[str, Any]],
        batch_size: int = 5,
        delay_between_batches: float = 1.0
    ) -> List[str]:
        """Send multiple emails in batches"""

        bulk_id = uuid.uuid4().hex[:8]
        all_request_ids = []

        print(f"📦 Starting bulk send: {len(email_templates)} emails")
        print(f"   Bulk ID: {bulk_id}")
        print(f"   Batch size: {batch_size}")
        print(f"   Batch delay: {delay_between_batches}s")
        print()

        # Process emails in batches
        for batch_start in range(0, len(email_templates), batch_size):
            batch_end = min(batch_start + batch_size, len(email_templates))
            batch_templates = email_templates[batch_start:batch_end]
            batch_number = (batch_start // batch_size) + 1
            total_batches = (len(email_templates) + batch_size - 1) // batch_size

            print(f"📤 Batch {batch_number}/{total_batches}: Sending {len(batch_templates)} emails...")

            # Send batch of emails concurrently
            batch_tasks = []
            for i, template in enumerate(batch_templates):
                job_index = batch_start + i
                email_job = self.create_email_job(
                    bulk_id=bulk_id,
                    job_index=job_index,
                    **template
                )
                task = self.send_email_job(email_job, show_details=False)
                batch_tasks.append(task)

            # Wait for batch to complete
            batch_request_ids = await asyncio.gather(*batch_tasks)
            all_request_ids.extend(batch_request_ids)

            print(f"   ✅ Batch {batch_number} completed: {len(batch_request_ids)} emails queued")

            # Delay between batches (except for the last one)
            if batch_end < len(email_templates):
                print(f"   ⏳ Waiting {delay_between_batches}s before next batch...")
                await asyncio.sleep(delay_between_batches)

        return all_request_ids


async def test_bulk_emails():
    """Test bulk email sending scenarios"""
    print("🚀 Starting Bulk Email Tests")
    print("=" * 50)

    tester = BulkEmailTester()

    try:
        await tester.connect()

        # Test Case 1: Newsletter to subscribers
        print("\n📧 Test Case 1: Newsletter Distribution")
        print("-" * 40)

        # Get multiple recipients from env
        multiple_recipients = os.getenv("TEST_MULTIPLE_EMAIL", os.getenv("TEST_EMAIL", "test@example.com")).split(",")

        newsletter_templates = []
        for i in range(1, 16):  # 15 subscribers
            # Cycle through multiple recipients
            recipient = multiple_recipients[i % len(multiple_recipients)]
            template = {
                "to_email": recipient,
                "subject": f"📰 Weekly Newsletter #{i:02d} - Bulk Test",
                "body": f"Hello Subscriber {i:02d}!\n\nWelcome to this week's newsletter.\n\nThis is a bulk email test to validate our email microservice performance.\n\n--- Newsletter Content ---\n\n• Feature updates this week\n• Performance improvements\n• New integrations\n• Bug fixes and optimizations\n\nThank you for subscribing!\n\nNewsletter Team",
                "body_html": f"""
                <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif;">
                    <header style="background: #2196F3; color: white; padding: 20px; text-align: center;">
                        <h1>📰 Weekly Newsletter #{i:02d}</h1>
                        <p>Bulk Email Test</p>
                    </header>

                    <main style="padding: 20px;">
                        <p>Hello <strong>Subscriber {i:02d}</strong>!</p>
                        <p>Welcome to this week's newsletter.</p>
                        <p><em>This is a bulk email test to validate our email microservice performance.</em></p>

                        <h3>📋 Newsletter Content</h3>
                        <ul>
                            <li>✨ Feature updates this week</li>
                            <li>🚀 Performance improvements</li>
                            <li>🔗 New integrations</li>
                            <li>🐛 Bug fixes and optimizations</li>
                        </ul>

                        <p>Thank you for subscribing!</p>
                    </main>

                    <footer style="background: #f0f0f0; padding: 15px; text-align: center; font-size: 12px;">
                        <p><strong>Newsletter Team</strong></p>
                        <p>Subscriber ID: {i:02d}</p>
                    </footer>
                </div>
                """,
                "priority": "low",
                "custom_headers": {
                    "X-Email-Type": "newsletter",
                    "X-Subscriber-ID": f"{i:02d}",
                    "X-Campaign": "weekly-newsletter"
                }
            }
            newsletter_templates.append(template)

        newsletter_ids = await tester.send_bulk_emails(
            newsletter_templates,
            batch_size=5,
            delay_between_batches=2.0
        )

        print(f"✅ Newsletter bulk send completed: {len(newsletter_ids)} emails queued")
        await asyncio.sleep(2)

        # Test Case 2: Personalized promotional emails
        print("\n📧 Test Case 2: Personalized Promotions")
        print("-" * 40)

        promotion_data = [
            {"name": "Alice", "discount": "20%", "category": "Electronics"},
            {"name": "Bob", "discount": "15%", "category": "Books"},
            {"name": "Charlie", "discount": "25%", "category": "Clothing"},
            {"name": "Diana", "discount": "30%", "category": "Home & Garden"},
            {"name": "Eve", "discount": "10%", "category": "Sports"},
            {"name": "Frank", "discount": "20%", "category": "Beauty"},
            {"name": "Grace", "discount": "35%", "category": "Tech Gadgets"},
            {"name": "Henry", "discount": "15%", "category": "Automotive"},
        ]

        promo_templates = []
        for i, promo in enumerate(promotion_data):
            recipient = multiple_recipients[i % len(multiple_recipients)]
            template = {
                "to_email": recipient,
                "subject": f"🎯 {promo['name']}, {promo['discount']} OFF {promo['category']}!",
                "body": f"Hi {promo['name']}!\n\nGreat news! You have a special {promo['discount']} discount on {promo['category']}.\n\nThis personalized offer is valid for the next 24 hours.\n\nDon't miss out on this exclusive deal!\n\nShopping Team",
                "body_html": f"""
                <div style="max-width: 500px; margin: 0 auto; font-family: Arial, sans-serif; border: 2px solid #FF9800; border-radius: 10px; overflow: hidden;">
                    <header style="background: linear-gradient(135deg, #FF9800, #F57C00); color: white; padding: 25px; text-align: center;">
                        <h1>🎯 Special Offer for {promo['name']}!</h1>
                    </header>

                    <main style="padding: 25px;">
                        <div style="background: #FFF3E0; border-left: 5px solid #FF9800; padding: 20px; margin: 20px 0;">
                            <h2 style="margin: 0; color: #E65100;">{promo['discount']} OFF</h2>
                            <h3 style="margin: 5px 0; color: #BF360C;">{promo['category']}</h3>
                        </div>

                        <p>Hi <strong>{promo['name']}</strong>!</p>
                        <p>Great news! You have a special discount waiting for you.</p>
                        <p style="background: #FFEBEE; padding: 15px; border-radius: 5px; text-align: center;">
                            <strong>This personalized offer is valid for the next 24 hours.</strong>
                        </p>
                        <p>Don't miss out on this exclusive deal!</p>
                    </main>

                    <footer style="background: #FFF3E0; padding: 15px; text-align: center; font-size: 12px;">
                        <p><strong>Shopping Team</strong></p>
                    </footer>
                </div>
                """,
                "priority": "normal",
                "custom_headers": {
                    "X-Email-Type": "promotion",
                    "X-Customer-Name": promo['name'],
                    "X-Discount-Amount": promo['discount'],
                    "X-Product-Category": promo['category']
                }
            }
            promo_templates.append(template)

        promo_ids = await tester.send_bulk_emails(
            promo_templates,
            batch_size=3,
            delay_between_batches=1.5
        )

        print(f"✅ Promotional bulk send completed: {len(promo_ids)} emails queued")
        await asyncio.sleep(1)

        # Test Case 3: System notifications
        print("\n📧 Test Case 3: System Notifications")
        print("-" * 40)

        notification_types = [
            {"type": "security", "priority": "high", "subject": "🔒 Security Alert"},
            {"type": "maintenance", "priority": "normal", "subject": "🔧 Scheduled Maintenance"},
            {"type": "update", "priority": "low", "subject": "📦 System Update"},
        ]

        notification_templates = []

        for notification in notification_types:
            for i, admin_email in enumerate(multiple_recipients):
                template = {
                    "to_email": admin_email,
                    "subject": f"{notification['subject']} - Admin {i+1}",
                    "body": f"System Notification\n\nNotification Type: {notification['type'].title()}\nPriority: {notification['priority'].title()}\nRecipient: Admin {i+1}\n\nThis is a bulk system notification test.\n\nSystem Administration",
                    "body_html": f"""
                    <div style="padding: 20px; border-left: 4px solid {'#f44336' if notification['priority'] == 'high' else '#ff9800' if notification['priority'] == 'normal' else '#4caf50'};">
                        <h2>{notification['subject']}</h2>
                        <p><strong>Notification Type:</strong> {notification['type'].title()}</p>
                        <p><strong>Priority:</strong> {notification['priority'].title()}</p>
                        <p><strong>Recipient:</strong> Admin {i+1}</p>
                        <hr>
                        <p><em>This is a bulk system notification test.</em></p>
                        <small>System Administration</small>
                    </div>
                    """,
                    "priority": notification['priority'],
                    "custom_headers": {
                        "X-Email-Type": "system-notification",
                        "X-Notification-Type": notification['type'],
                        "X-Admin-ID": str(i+1)
                    }
                }
                notification_templates.append(template)

        notification_ids = await tester.send_bulk_emails(
            notification_templates,
            batch_size=4,
            delay_between_batches=0.5
        )

        print(f"✅ System notifications bulk send completed: {len(notification_ids)} emails queued")

        # Final summary
        print("\n" + "=" * 50)
        print("🎉 All Bulk Email Tests Completed!")
        print("=" * 50)

        total_emails = len(newsletter_ids) + len(promo_ids) + len(notification_ids)

        print("\n📊 Bulk Test Summary:")
        print(f"   📰 Newsletter emails: {len(newsletter_ids)}")
        print(f"   🎯 Promotional emails: {len(promo_ids)}")
        print(f"   🔔 System notifications: {len(notification_ids)}")
        print(f"   📧 Total emails queued: {total_emails}")

        print("\n🔍 Database query:")
        print("   SELECT status, COUNT(*) FROM email_jobs WHERE source_service = 'bulk-email-tester' GROUP BY status")

        current_time = datetime.utcnow()
        print(f"\n⏰ Bulk send completed at: {current_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    except Exception as e:
        print(f"💥 Test failed: {e}")
        sys.exit(1)

    finally:
        await tester.close()


def print_usage():
    """Print usage instructions"""
    print("📧 Bulk Email Test Script")
    print("=" * 30)
    print()
    print("Tests bulk email sending by queuing multiple jobs:")
    print("   • Newsletter distribution (15 emails)")
    print("   • Personalized promotions (8 emails)")
    print("   • System notifications (9 emails)")
    print("   • Batched sending with delays")
    print()
    print("🔧 Required .env variables:")
    print("   RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASSWORD")
    print("   SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD")
    print()
    print("🚀 Usage:")
    print("   python send_bulk_emails.py")
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help", "help"]:
        print_usage()
        sys.exit(0)

    print("🧪 Email Service - Bulk Email Test")
    print("🕐", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print()

    # Verify required environment variables
    required_vars = ["RABBITMQ_HOST", "SMTP_USER", "SMTP_PASSWORD"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("   Please check your .env file")
        sys.exit(1)

    print(f"📊 This test will send ~32 emails in batches")
    print(f"   Make sure your SMTP provider can handle the load")
    print()

    asyncio.run(test_bulk_emails())