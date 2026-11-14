"""
Seed data script for CrewLink demo.

Creates:
- 2 locals (Local 27 with ~2000 members, Local 42 with ~200 members)
- 3-4 classifications per local
- 1 leadership + 1 member login per local
- 1 already-sent announcement in Local 27 with recipient rows
"""
import random
import uuid
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Local, Member, User, Announcement, AnnouncementRecipient

# Fixed UUIDs for test accounts (so README can reference them)
SEEDED_ANNOUNCEMENT_ID = uuid.UUID('11111111-1111-1111-1111-111111111111')
LOCAL_42_TEST_MEMBER_ID = uuid.UUID('22222222-2222-2222-2222-222222222222')


CLASSIFICATIONS = [
    'Journeyman Wireman',
    'Apprentice 1st Year',
    'Apprentice 2nd Year',
    'Apprentice 3rd Year',
]

FIRST_NAMES = [
    'James', 'John', 'Robert', 'Michael', 'William', 'David', 'Joseph', 'Thomas',
    'Maria', 'Jennifer', 'Patricia', 'Linda', 'Elizabeth', 'Susan', 'Jessica', 'Sarah',
    'Carlos', 'Miguel', 'Ahmed', 'Wei', 'Yuki', 'Olga', 'Hans', 'Pierre',
]

LAST_NAMES = [
    'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
    'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson',
    'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Thompson', 'White',
]


class Command(BaseCommand):
    help = 'Seed database with demo data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database...')

        # Clear existing data
        self.stdout.write('Clearing existing data...')
        AnnouncementRecipient.objects.all().delete()
        Announcement.objects.all().delete()
        User.objects.all().delete()  # Clear all users including admin
        Member.objects.all().delete()
        Local.objects.all().delete()

        # Create locals
        self.stdout.write('Creating locals...')
        local_27 = Local.objects.create(name='Local 27')
        local_42 = Local.objects.create(name='Local 42')

        # Create members for Local 27 (~2000)
        self.stdout.write('Creating members for Local 27 (2000)...')
        members_27 = self._create_members(local_27, 2000)

        # Create members for Local 42 (~200)
        # First member has fixed UUID for testing
        self.stdout.write('Creating members for Local 42 (200)...')
        first_member_42 = Member.objects.create(
            id=LOCAL_42_TEST_MEMBER_ID,
            local=local_42,
            full_name='Test Member',
            email='test.member@example.com',
            classification='Journeyman Wireman',
            status='active'
        )
        rest_members_42 = self._create_members(local_42, 199)
        members_42 = [first_member_42] + list(rest_members_42)

        # Create leadership accounts
        self.stdout.write('Creating user accounts...')

        # Local 27 leadership
        leader_27 = User.objects.create_user(
            email='leader@local27.union',
            password='password123',
            role='leadership',
            local=local_27
        )

        # Local 27 member (link to first member)
        member_user_27 = User.objects.create_user(
            email='member@local27.union',
            password='password123',
            role='member',
            local=local_27,
            member=members_27[0]
        )

        # Local 42 leadership
        leader_42 = User.objects.create_user(
            email='leader@local42.union',
            password='password123',
            role='leadership',
            local=local_42
        )

        # Local 42 member
        member_user_42 = User.objects.create_user(
            email='member@local42.union',
            password='password123',
            role='member',
            local=local_42,
            member=members_42[0]
        )

        # Admin superuser
        admin = User.objects.create_superuser(
            email='admin@crewlink.com',
            password='admin123'
        )

        # Create a sent announcement in Local 27 (with fixed UUID for testing)
        self.stdout.write('Creating sent announcement in Local 27...')
        announcement = Announcement.objects.create(
            id=SEEDED_ANNOUNCEMENT_ID,
            local=local_27,
            created_by=leader_27,
            title='Emergency Meeting - Contractor Situation',
            body='All members are required to attend the emergency meeting regarding the ongoing contractor dispute. We need full attendance to discuss our response.',
            push_preview='Emergency meeting Thursday 6pm at the hall. All members required.',
            needs_ack=True,
            status='sent',
            approved_by=leader_27,
            approved_at=timezone.now(),
            sent_at=timezone.now()
        )

        # Create recipient rows for all Local 27 members
        self.stdout.write('Creating recipient rows...')
        recipients = []
        for i, member in enumerate(members_27):
            # Simulate some having read/acked
            read_at = None
            acked_at = None

            if i < 1500:  # 75% sent
                sent_at = timezone.now()
                if i < 1000:  # 50% read
                    read_at = timezone.now()
                if i < 500:  # 25% acked
                    acked_at = timezone.now()
            else:
                sent_at = timezone.now()

            recipients.append(AnnouncementRecipient(
                announcement=announcement,
                member=member,
                local=local_27,
                status='sent',
                sent_at=sent_at,
                read_at=read_at,
                acked_at=acked_at
            ))

        AnnouncementRecipient.objects.bulk_create(recipients)

        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== SEED DATA COMPLETE ==='))
        self.stdout.write(f'\nLocals:')
        self.stdout.write(f'  - Local 27: {local_27.id} ({len(members_27)} members)')
        self.stdout.write(f'  - Local 42: {local_42.id} ({len(members_42)} members)')

        self.stdout.write(f'\nTest Accounts (password: password123):')
        self.stdout.write(f'  Local 27 Leadership: leader@local27.union')
        self.stdout.write(f'  Local 27 Member:     member@local27.union')
        self.stdout.write(f'  Local 42 Leadership: leader@local42.union')
        self.stdout.write(f'  Local 42 Member:     member@local42.union')

        self.stdout.write(f'\nAdmin Account (password: admin123):')
        self.stdout.write(f'  Django Admin: admin@crewlink.com')
        self.stdout.write(f'  URL: http://localhost:8000/admin')

        self.stdout.write(f'\nSent Announcement:')
        self.stdout.write(f'  ID: {announcement.id}')
        self.stdout.write(f'  Title: {announcement.title}')

        self.stdout.write(f'\nMember in Local 42 (for Rule 1 test):')
        self.stdout.write(f'  ID: {members_42[0].id}')

    def _create_members(self, local, count):
        members = []
        for i in range(count):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            classification = random.choice(CLASSIFICATIONS)

            members.append(Member(
                local=local,
                full_name=f'{first} {last}',
                email=f'{first.lower()}.{last.lower()}.{i}@example.com',
                classification=classification,
                status='active'
            ))

        return Member.objects.bulk_create(members)
