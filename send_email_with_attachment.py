#!/usr/bin/env python3
"""
Email with Attachment Test Script
Tests email sending with attachments (both base64 and URL modes)
"""

import asyncio
import json
import uuid
import base64
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

import aio_pika
from aio_pika import Message
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import crypto helper for password encryption
from crypto_helper import encrypt_smtp_password


class EmailWithAttachmentTester:
    """Email service tester with attachment support"""

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
            print("🔌 Connecting to RabbitMQ...")
            self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
            self.channel = await self.connection.channel()
            print(f"✅ Connected to RabbitMQ, queue: {self.queue_name}")
        except Exception as e:
            print(f"❌ Failed to connect to RabbitMQ: {e}")
            raise

    async def close(self):
        """Close RabbitMQ connection"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            print("✅ RabbitMQ connection closed")

    def create_attachment_base64(self, file_path: str) -> Dict[str, Any]:
        """
        Create base64 attachment from file

        Args:
            file_path: Path to file

        Returns:
            Attachment dict for email job
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read file
        with open(path, 'rb') as f:
            file_content = f.read()

        # Encode to base64
        base64_content = base64.b64encode(file_content).decode('utf-8')

        # Determine content type
        content_types = {
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.txt': 'text/plain',
            '.csv': 'text/csv',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.zip': 'application/zip',
        }

        content_type = content_types.get(path.suffix.lower(), 'application/octet-stream')

        print(f"📎 Created base64 attachment:")
        print(f"   File: {path.name}")
        print(f"   Size: {len(file_content):,} bytes ({len(file_content)/1024/1024:.2f} MB)")
        print(f"   Type: {content_type}")
        print(f"   Base64 length: {len(base64_content):,} chars")

        return {
            "filename": path.name,
            "content_type": content_type,
            "content": base64_content,
            "mode": "base64",
            "size_bytes": len(file_content)
        }

    def create_attachment_url(self, url: str, filename: str, content_type: str, size_bytes: int) -> Dict[str, Any]:
        """
        Create URL attachment (for S3 or public URLs)

        Args:
            url: Public or pre-signed URL to file
            filename: Filename for attachment
            content_type: MIME content type
            size_bytes: File size in bytes

        Returns:
            Attachment dict for email job
        """
        print(f"🌐 Created URL attachment:")
        print(f"   File: {filename}")
        print(f"   URL: {url[:50]}...")
        print(f"   Type: {content_type}")
        print(f"   Size: {size_bytes:,} bytes ({size_bytes/1024/1024:.2f} MB)")

        return {
            "filename": filename,
            "content_type": content_type,
            "url": url,
            "mode": "url",
            "size_bytes": size_bytes
        }

    def create_email_job(
        self,
        to_emails: list[str],
        subject: str,
        body: str,
        body_html: str = "",
        attachments: list[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create email job payload with attachments"""

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
            "from_name": "Email Service Test (Attachment)",
            "from_email": os.getenv("SMTP_USER"),
            "use_tls": True,
            "use_ssl": False,
            "timeout": 30
        }

        # Default metadata
        request_id = str(uuid.uuid4())
        metadata = {
            "source_app": "email-service-tester-attachment",
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
            "smtp": smtp_config,
            "metadata": metadata
        }

        # Add HTML body if provided
        if body_html:
            email_job["email"]["body_html"] = body_html

        # Add attachments if provided
        if attachments:
            email_job["email"]["attachments"] = attachments

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
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )

            # Send to queue
            await self.channel.default_exchange.publish(
                message,
                routing_key=self.queue_name
            )

            request_id = email_job["metadata"]["request_id"]
            print(f"✅ Email job queued successfully!")
            print(f"📧 Request ID: {request_id}")
            print(f"👥 Recipients: {', '.join(email_job['email']['to'])}")
            print(f"📝 Subject: {email_job['email']['subject']}")

            if 'attachments' in email_job['email']:
                print(f"📎 Attachments: {len(email_job['email']['attachments'])} file(s)")

            return request_id

        except Exception as e:
            print(f"❌ Failed to send email job: {e}")
            raise


async def test_email_with_attachment_base64():
    """Test sending email with base64 attachment"""
    print("🚀 Starting Email with Base64 Attachment Test")
    print("=" * 60)

    tester = EmailWithAttachmentTester()

    try:
        # Connect to RabbitMQ
        await tester.connect()

        # Ask user for file path or create sample file
        print("\n📁 Attachment Options:")
        print("1. Enter path to existing file")
        print("2. Create sample text file")
        choice = input("\nChoose option (1 or 2, default: 2): ").strip() or "2"

        if choice == "1":
            file_path = input("Enter file path: ").strip()
        else:
            # Create sample file
            file_path = "sample_attachment.txt"
            with open(file_path, 'w') as f:
                f.write("This is a sample attachment file.\n")
                f.write(f"Generated at: {datetime.now()}\n")
                f.write("\nThis email was sent via the email microservice ")
                f.write("with attachment support!\n")
            print(f"✅ Created sample file: {file_path}")

        # Create base64 attachment
        print("\n📎 Processing attachment...")
        attachment = tester.create_attachment_base64(file_path)

        # Create email job
        print("\n📧 Creating email job...")
        email_job = tester.create_email_job(
            to_emails=[os.getenv("TEST_EMAIL", "test@example.com")],
            subject="Test Email with Attachment (Base64 Mode)",
            body="Hello! This email includes an attachment.\n\nThe file is embedded as base64 in the email.",
            body_html="""
            <h2>Test Email with Attachment</h2>
            <p>Hello! This email includes an <strong>attachment</strong>.</p>
            <p>The file is embedded as <code>base64</code> in the email.</p>
            <hr>
            <small>Generated by email-service-tester</small>
            """,
            attachments=[attachment]
        )

        # Send email job
        print("\n📤 Sending email job to queue...")
        request_id = await tester.send_email_job(email_job)

        print("\n🎉 Test completed successfully!")
        print(f"📋 Request ID: {request_id}")
        print("\n📌 Next steps:")
        print("   1. Check email service logs for processing")
        print("   2. Check recipient inbox for email with attachment")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)

    finally:
        await tester.close()


async def test_email_with_attachment_url():
    """Test sending email with URL attachment"""
    print("🚀 Starting Email with URL Attachment Test")
    print("=" * 60)

    tester = EmailWithAttachmentTester()

    try:
        await tester.connect()

        print("\n🌐 URL Attachment Mode")
        print("This mode requires a publicly accessible URL or pre-signed S3 URL")
        print()

        # Get URL from user
        url = input("Enter file URL: ").strip()
        if not url:
            print("❌ URL is required")
            return

        filename = input("Enter filename (e.g., report.pdf): ").strip()
        if not filename:
            filename = "document.pdf"

        content_type = input("Enter content type (default: application/pdf): ").strip()
        if not content_type:
            content_type = "application/pdf"

        size_input = input("Enter file size in bytes (optional): ").strip()
        size_bytes = int(size_input) if size_input else 0

        # Create URL attachment
        attachment = tester.create_attachment_url(url, filename, content_type, size_bytes)

        # Create email job
        email_job = tester.create_email_job(
            to_emails=[os.getenv("TEST_EMAIL", "test@example.com")],
            subject="Test Email with Attachment (URL Mode)",
            body="Hello! This email includes an attachment downloaded from URL.",
            body_html="""
            <h2>Test Email with Attachment (URL Mode)</h2>
            <p>Hello! This email includes an attachment downloaded from a URL.</p>
            <p>The file is downloaded by the email service and attached.</p>
            <hr>
            <small>Generated by email-service-tester</small>
            """,
            attachments=[attachment]
        )

        # Send email job
        print("\n📤 Sending email job to queue...")
        request_id = await tester.send_email_job(email_job)

        print("\n🎉 Test completed successfully!")
        print(f"📋 Request ID: {request_id}")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)

    finally:
        await tester.close()


if __name__ == "__main__":
    print("📧 Email Service - Attachment Test")
    print("⏰", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print()

    # Check critical environment variables
    if not os.getenv("SMTP_USER") or not os.getenv("SMTP_PASSWORD"):
        print("⚠️  Warning: SMTP credentials not set")
        print()

    # Choose test mode
    print("Select attachment mode:")
    print("1. Base64 mode (small files, embedded)")
    print("2. URL mode (large files, download from URL)")
    mode = input("\nChoose mode (1 or 2, default: 1): ").strip() or "1"

    if mode == "2":
        asyncio.run(test_email_with_attachment_url())
    else:
        asyncio.run(test_email_with_attachment_base64())