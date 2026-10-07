from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import personal_birthday
import server


class BirthdayScheduleTests(unittest.TestCase):
    def instant(self, value):
        return datetime.fromisoformat(value.replace('Z','+00:00'))

    def test_october_ten_activates_at_india_midnight(self):
        before=personal_birthday.context(now=self.instant('2026-10-09T18:29:59Z'))
        start=personal_birthday.context(now=self.instant('2026-10-09T18:30:00Z'))
        last=personal_birthday.context(now=self.instant('2026-10-10T18:29:59Z'))
        after=personal_birthday.context(now=self.instant('2026-10-10T18:30:00Z'))
        self.assertFalse(before['active'])
        self.assertTrue(start['active'])
        self.assertEqual(start['occasion'],'birthday')
        self.assertEqual(start['today'],'2026-10-10')
        self.assertTrue(last['active'])
        self.assertFalse(after['active'])
        self.assertEqual(after['eventDate'],'2027-10-10')

    def test_today_preview_expires_and_does_not_replace_annual_birthday(self):
        during=personal_birthday.context(preview_date='2026-09-30',now=self.instant('2026-09-30T16:00:00Z'))
        after=personal_birthday.context(preview_date='2026-09-30',now=self.instant('2026-09-30T18:30:00Z'))
        birthday=personal_birthday.context(preview_date='2026-09-30',now=self.instant('2026-10-10T07:00:00Z'))
        self.assertEqual(during['occasion'],'preview')
        self.assertTrue(during['active'])
        self.assertFalse(after['active'])
        self.assertEqual(birthday['occasion'],'birthday')
        self.assertEqual(personal_birthday.context(now=self.instant('2027-10-10T00:00:00Z'))['occasion'],'birthday')

    def test_off_disables_automatic_birthday_and_preview(self):
        self.assertFalse(personal_birthday.context('off','2026-10-10',self.instant('2026-10-10T00:00:00Z'))['active'])
        self.assertFalse(personal_birthday.context('off','2026-09-30',self.instant('2026-09-30T05:00:00Z'))['active'])

    def test_only_owner_can_change_preview_and_note_flag_is_independent(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(server,'DATA',Path(directory)):
            server.initialize_database()
            server.set_setting('sorry_enabled','off')
            with patch.object(server,'owner_panel') as panel:
                server.handle_command(-1,'/surprise today')
                panel.assert_not_called()
                self.assertEqual(server.setting('surprise_preview_date'),'')
                server.handle_command(server.OWNER,'/surprise today')
                self.assertEqual(server.setting('surprise_preview_date'),personal_birthday.today())
                self.assertEqual(server.setting('sorry_enabled'),'off')
                server.handle_command(server.OWNER,'/surprise auto')
                self.assertEqual(server.setting('surprise_preview_date'),'')
                server.handle_command(server.OWNER,'/surprise off')
                self.assertEqual(server.setting('surprise_mode'),'off')


if __name__=='__main__':
    unittest.main()
