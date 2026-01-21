#!/usr/bin/env python3
"""
Multiple Recipients Email Test Script
Tests email sending with multiple TO, CC, BCC recipients and different priorities
"""

import asyncio
import json
import uuid
from datetime import datetime
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


class MultipleRecipientsEmailTester:
    """Email service tester for multiple recipients scenarios"""

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

    def create_multi_recipient_email(
        self,
        to_emails: List[str],
        cc_emails: List[str] = None,
        bcc_emails: List[str] = None,
        subject: str = "",
        body: str = "",
        body_html: str = "",
        priority: str = "normal",
        custom_headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Create multi-recipient email job with advanced features"""

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
            "from_name": "Multi-Recipient Test",
            "from_email": os.getenv("SMTP_USER"),  # Use same as user for Gmail
            "use_tls": True,
            "use_ssl": False,
            "timeout": 45  # Longer timeout for multiple recipients
        }

        # Request tracking
        request_id = f"multi_{uuid.uuid4().hex[:8]}"
        metadata = {
            "source_app": "multi-recipient-tester",
            "request_id": request_id,
            "queued_at": datetime.utcnow().isoformat() + "Z"
        }

        # Build email structure
        email_data = {
            "to": to_emails,
            "subject": subject,
            "body": body,
            "priority": priority  # low, normal, high
        }

        # Add optional recipients
        if cc_emails:
            email_data["cc"] = cc_emails
        if bcc_emails:
            email_data["bcc"] = bcc_emails

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
            email_data = email_job["email"]

            print(f"✅ Multi-recipient email queued!")
            print(f"📧 Request ID: {request_id}")
            print(f"📬 TO ({len(email_data['to'])}): {', '.join(email_data['to'])}")

            if "cc" in email_data:
                print(f"📋 CC ({len(email_data['cc'])}): {', '.join(email_data['cc'])}")
            if "bcc" in email_data:
                print(f"📨 BCC ({len(email_data['bcc'])}): {', '.join(email_data['bcc'])}")

            total_recipients = len(email_data['to']) + len(email_data.get('cc', [])) + len(email_data.get('bcc', []))
            print(f"👥 Total Recipients: {total_recipients}")
            print(f"⚡ Priority: {email_data['priority']}")

            return request_id

        except Exception as e:
            print(f"❌ Failed to send email job: {e}")
            raise


async def test_multiple_recipients():
    """Test various multiple recipient scenarios"""
    print("🚀 Starting Multiple Recipients Email Test")
    print("=" * 60)

    tester = MultipleRecipientsEmailTester()

    try:
        await tester.connect()

        # Test Case 1: Multiple TO recipients with normal priority
        print("\n📧 Test Case 1: Multiple TO Recipients")
        print("-" * 40)

        # Get multiple recipients from env
        multiple_recipients = os.getenv("TEST_MULTIPLE_EMAIL", "test@example.com").split(",")

        email_job1 = tester.create_multi_recipient_email(
            to_emails=multiple_recipients,
            subject="Team Notification - Multiple Recipients Test",
            body="Hello team!\n\nThis is a test email sent to multiple recipients simultaneously.\n\nBest regards,\nEmail Service Test",
            body_html="""
            <h2>🔔 Team Notification</h2>
            <p>Hello team!</p>
            <p>This is a test email sent to <strong>multiple recipients</strong> simultaneously.</p>
            <ul>
                <li>Feature: Multiple TO recipients</li>
                <li>Priority: Normal</li>
                <li>Content: HTML + Plain text</li>
            </ul>
            <p>Best regards,<br><em>Email Service Test</em></p>
            """,
            priority="normal",
            custom_headers={
                "X-Test-Case": "multiple-recipients-1",
                "X-Notification-Type": "team-update"
            }
        )

        request_id1 = await tester.send_email_job(email_job1)
        await asyncio.sleep(1)  # Brief pause between tests

        # Test Case 2: TO + CC + BCC with high priority
        print("\n📧 Test Case 2: TO + CC + BCC Recipients")
        print("-" * 40)

        email_job2 = tester.create_multi_recipient_email(
            to_emails=[multiple_recipients[0]],
            cc_emails=[multiple_recipients[1] if len(multiple_recipients) > 1 else multiple_recipients[0]],
            bcc_emails=[os.getenv("TEST_EMAIL")],
            subject="🔥 URGENT: High Priority Multi-Recipient Test",
            body="URGENT MESSAGE\n\nThis is a high-priority test with TO, CC, and BCC recipients.\n\n- TO: Primary recipient\n- CC: Management visibility\n- BCC: Audit trail\n\nImmediate action required for testing purposes.",
            body_html="""
            <div style="border-left: 4px solid #ff4444; padding: 20px; background: #fff5f5;">
                <h2 style="color: #cc0000;">🔥 URGENT: High Priority Test</h2>
                <p><strong>This is a high-priority test with multiple recipient types.</strong></p>

                <table style="width: 100%; margin: 20px 0;">
                    <tr><td><strong>TO:</strong></td><td>Primary recipient</td></tr>
                    <tr><td><strong>CC:</strong></td><td>Management visibility</td></tr>
                    <tr><td><strong>BCC:</strong></td><td>Audit trail</td></tr>
                </table>

                <p style="color: #cc0000;"><strong>Immediate action required for testing purposes.</strong></p>
            </div>
            """,
            priority="high",
            custom_headers={
                "X-Test-Case": "multiple-recipients-2",
                "X-Priority-Level": "urgent",
                "X-Recipient-Types": "to-cc-bcc"
            }
        )

        request_id2 = await tester.send_email_job(email_job2)
        await asyncio.sleep(1)

        # Test Case 3: Large distribution list with low priority
        print("\n📧 Test Case 3: Large Distribution List")
        print("-" * 40)

        email_job3 = tester.create_multi_recipient_email(
            to_emails=multiple_recipients,
            subject="📰 Newsletter: Multi-Recipient Distribution Test",
            body="Weekly Newsletter\n\nHello subscribers!\n\nThis is our weekly newsletter being tested with a large distribution list.\n\nContents:\n- Feature updates\n- Performance improvements\n- Testing scenarios\n\nThank you for subscribing!\n\nNewsletter Team",
            body_html="""
            <div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif;">
                <header style="background: #4CAF50; color: white; padding: 20px; text-align: center;">
                    <h1>📰 Weekly Newsletter</h1>
                </header>

                <main style="padding: 20px;">
                    <p>Hello subscribers!</p>
                    <p>This is our weekly newsletter being tested with a <strong>large distribution list</strong>.</p>

                    <h3>📋 This Week's Contents:</h3>
                    <ul>
                        <li>✨ Feature updates</li>
                        <li>🚀 Performance improvements</li>
                        <li>🧪 Testing scenarios</li>
                    </ul>

                    <p>Thank you for subscribing!</p>
                </main>

                <footer style="background: #f0f0f0; padding: 15px; text-align: center; font-size: 12px;">
                    <p><em>Newsletter Team</em> | Email Service Test</p>
                </footer>
            </div>
            """,
            priority="low",  # Low priority for bulk newsletters
            custom_headers={
                "X-Test-Case": "multiple-recipients-3",
                "X-Email-Type": "newsletter",
                "X-Bulk-Send": "true",
                "List-Unsubscribe": "<mailto:unsubscribe@example.com>"
            }
        )

        request_id3 = await tester.send_email_job(email_job3)

        # Test summary
        print("\n" + "=" * 60)
        print("🎉 All Multiple Recipients Tests Completed!")
        print("=" * 60)

        print("\n📊 Test Summary:")
        print(f"   Test 1: {request_id1} - 3 TO recipients (normal priority)")
        print(f"   Test 2: {request_id2} - TO+CC+BCC (high priority)")
        print(f"   Test 3: {request_id3} - 10 recipients (low priority)")

        print("\n🔍 Database query:")
        print("   SELECT id, subject, priority, status FROM email_jobs WHERE source_service = 'multi-recipient-tester'")

    except Exception as e:
        print(f"💥 Test failed: {e}")
        sys.exit(1)

    finally:
        await tester.close()


def print_usage():
    """Print usage instructions"""
    print("📧 Multiple Recipients Email Test Script")
    print("=" * 45)
    print()
    print("Tests various multiple recipient scenarios:")
    print("   • Multiple TO recipients")
    print("   • TO + CC + BCC combinations")
    print("   • Large distribution lists")
    print("   • Different priority levels")
    print("   • Custom headers")
    print()
    print("🔧 Environment Variables:")
    print("   SMTP_USER        - SMTP username")
    print("   SMTP_PASSWORD    - SMTP password")
    print("   SMTP_FROM        - From email address")
    print("   RABBITMQ_URL     - RabbitMQ connection URL")
    print()
    print("🚀 Usage:")
    print("   python send_multiple_recipients.py")
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help", "help"]:
        print_usage()
        sys.exit(0)

    print("🧪 Email Service - Multiple Recipients Test")
    print("🕐", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print()

    if not os.getenv("SMTP_USER") or not os.getenv("SMTP_PASSWORD"):
        print("⚠️  Warning: SMTP credentials not set in environment variables")
        print("   Tests will queue but may fail to send without proper SMTP config")
        print()

    asyncio.run(test_multiple_recipients())