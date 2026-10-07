from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import birthday_names
import server


class BirthdayNameTests(unittest.TestCase):
    def test_plain_name_and_optional_korean_spelling(self):
        self.assertEqual(birthday_names.parse('Arjun Kumar'),{'name':'Arjun Kumar','koreanName':'Arjun Kumar'})
        self.assertEqual(birthday_names.parse('Shivani'),{'name':'Shivani','koreanName':'시바니'})
        self.assertEqual(birthday_names.parse('Arjun | 아르준'),{'name':'Arjun','koreanName':'아르준'})
        self.assertEqual(birthday_names.parse('आरव')['name'],'आरव')
        self.assertEqual(birthday_names.parse("Mary O’Connor")['name'],"Mary O’Connor")

    def test_invalid_names_are_rejected(self):
        for value in ['', '<script>alert(1)</script>', 'A\nB', 'A'*51, 'Name |', 'A | B | C', '123']:
            with self.subTest(value=value),self.assertRaises(ValueError):birthday_names.parse(value)

    def test_only_owner_can_update_and_setting_survives_new_connection(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(server,'DATA',Path(directory)),patch.object(server,'reply') as reply:
            server.initialize_database();server.set_setting('sorry_enabled','off')
            server.handle_command(-1,'/name Someone else')
            reply.assert_not_called();self.assertEqual(server.setting('birthday_name'),'')
            server.handle_command(server.OWNER,'/name Arjun Kumar | 아르준 쿠마르')
            self.assertEqual(birthday_names.current(server.setting),{'name':'Arjun Kumar','koreanName':'아르준 쿠마르'})
            self.assertEqual(server.setting('sorry_enabled'),'off')
            server.handle_command(server.OWNER,'/name <bad>')
            self.assertEqual(server.setting('birthday_name'),'Arjun Kumar')
            server.handle_command(server.OWNER,'/name')
            self.assertIn('Arjun Kumar',reply.call_args.args[1])


if __name__=='__main__':unittest.main()
