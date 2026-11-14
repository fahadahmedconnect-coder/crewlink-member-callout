"""
Background worker to process announcement sends.

This worker:
1. Finds announcements with status='sending'
2. Creates recipient rows for all active members
3. Claims batches using FOR UPDATE SKIP LOCKED
4. Simulates sending push notifications
5. Updates status to 'sent' when complete

Rule 2 enforcement:
- UNIQUE constraint on (announcement_id, member_id) prevents duplicates
- FOR UPDATE SKIP LOCKED prevents two workers claiming same batch
- ON CONFLICT DO NOTHING handles race conditions on insert
"""
import time
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone
from core.models import Announcement, AnnouncementRecipient, Member


BATCH_SIZE = 500
SLEEP_SECONDS = 1


class Command(BaseCommand):
    help = 'Process announcement sends in background'

    def handle(self, *args, **options):
        self.stdout.write('Starting send worker...')
        self.stdout.write(f'Batch size: {BATCH_SIZE}')
        self.stdout.write('Press Ctrl+C to stop\n')

        while True:
            try:
                self._process_pending_announcements()
                time.sleep(SLEEP_SECONDS)
            except KeyboardInterrupt:
                self.stdout.write('\nStopping worker...')
                break
            except Exception as e:
                self.stderr.write(f'Error: {e}')
                time.sleep(SLEEP_SECONDS)

    def _process_pending_announcements(self):
        """Find and process announcements that need sending"""
        announcements = Announcement.objects.filter(status='sending')

        for announcement in announcements:
            self.stdout.write(f'Processing announcement: {announcement.id}')
            self._create_recipients(announcement)
            self._send_batches(announcement)
            self._check_completion(announcement)

    def _create_recipients(self, announcement):
        """
        Bulk create recipient rows for all active members.
        Uses ON CONFLICT DO NOTHING for Rule 2.
        """
        # Build filter for members
        member_filter = {
            'local_id': announcement.local_id,
            'status': 'active'
        }

        # Optional classification filter
        if announcement.target_classification:
            member_filter['classification'] = announcement.target_classification

        # Check if recipients already exist
        existing_count = AnnouncementRecipient.objects.filter(
            announcement=announcement
        ).count()

        if existing_count > 0:
            return  # Already created

        # Get all members and create recipients
        members = Member.objects.filter(**member_filter)

        recipients = [
            AnnouncementRecipient(
                announcement=announcement,
                member=member,
                local_id=announcement.local_id,
                status='pending'
            )
            for member in members
        ]

        # Bulk create with ignore_conflicts (ON CONFLICT DO NOTHING)
        AnnouncementRecipient.objects.bulk_create(
            recipients,
            ignore_conflicts=True  # Rule 2: skip duplicates
        )

        self.stdout.write(f'  Created {len(recipients)} recipient rows')

    def _send_batches(self, announcement):
        """
        Claim and process batches of recipients.
        Uses FOR UPDATE SKIP LOCKED to prevent worker collision.
        """
        while True:
            with transaction.atomic():
                # Claim batch using raw SQL for SKIP LOCKED
                # Django ORM doesn't support SKIP LOCKED directly
                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE core_announcementrecipient
                        SET status = 'sending'
                        WHERE id IN (
                            SELECT id FROM core_announcementrecipient
                            WHERE announcement_id = %s AND status = 'pending'
                            LIMIT %s
                            FOR UPDATE SKIP LOCKED
                        )
                        RETURNING id
                    """, [str(announcement.id), BATCH_SIZE])

                    claimed_ids = [row[0] for row in cursor.fetchall()]

                if not claimed_ids:
                    break  # No more pending

                # Process claimed recipients
                recipients = AnnouncementRecipient.objects.filter(
                    id__in=claimed_ids
                ).select_related('member')

                for recipient in recipients:
                    # Simulate push notification
                    self.stdout.write(f'    PUSH: {recipient.member.email}')

                    # Mark as sent
                    recipient.status = 'sent'
                    recipient.sent_at = timezone.now()
                    recipient.save(update_fields=['status', 'sent_at'])

                self.stdout.write(f'  Processed batch of {len(claimed_ids)}')

    def _check_completion(self, announcement):
        """Check if all recipients are sent and update announcement status"""
        pending_count = AnnouncementRecipient.objects.filter(
            announcement=announcement,
            status__in=['pending', 'sending']
        ).count()

        if pending_count == 0:
            announcement.status = 'sent'
            announcement.save(update_fields=['status'])
            self.stdout.write(self.style.SUCCESS(
                f'  Announcement {announcement.id} complete!'
            ))
