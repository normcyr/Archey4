
import os
import tempfile
import unittest
from subprocess import Popen, check_output
from unittest.mock import patch

from archey.archey import LAN_IP


# --------------------------------------------------------------------------------

class FakePopenMock(object):
    """
    This is the trick :
    * We mock the `Popen` object of this very module.
    * We use a temp file as a fake pipe, and make `Popen` return it.
    * The mock object of the original module (here: `archey.archey.Popen`)
        either receive our mocked mock, or an "original" `Popen` instance
        (called with the passed arguments to imitate the default behavior).
    """
    @patch('subprocess.Popen')
    def __init__(self, stdout_mock, popen_mock):
        self.stdout_mock = stdout_mock

        # A typical `ip -o addr show up` output
        self.stdout_mock.write(b"""\
1: lo    inet 127.0.0.1/8 scope host lo\\       valid_lft forever \
preferred_lft forever
1: lo    inet6 ::1/128 scope host \\       valid_lft forever \
preferred_lft forever
2: eth0    inet XXX.YYY.ZZZ.9/24 brd XXX.YYY.ZZZ.255 scope global \
dynamic eth0\\       valid_lft 2100sec preferred_lft 2100sec
2: eth0    inet6 0123::456:789a:bde:27cc/64 scope link \\       \
valid_lft forever preferred_lft forever
4: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global \ \
docker0\\       valid_lft forever preferred_lft forever
4: docker0    inet6 0123::45:6789:abcd:6817/64 scope global \\       \
valid_lft forever preferred_lft forever
""")
        self.stdout_mock.seek(0)

        # Our `Popen` mock will return the fake FIFO above
        popen_mock.return_value.stdout = self.stdout_mock

        # The first call will be "mocked" but not the other ones.
        self.answers = [
            popen_mock,
            Popen,
            Popen,
            Popen
        ]

    def method(self, *args, **kwargs):
        return self.answers.pop(0)(*args, **kwargs)


class FakeCheckOutputMock(object):
    """
    Same stuff over here, the first `check_output` call will fail,
      and the second one will take back its default behavior.
    """
    def __init__(self):
        self.answers = [
            (True, FileNotFoundError()),
            (False, check_output)
        ]

    def method(self, *args, **kwargs):
        answer = self.answers.pop(0)

        # Do we have to mock this entity ? Or should we run a "regular" call ?
        if answer[0]:
            # Handles exceptions and "regular" values differently
            if issubclass(answer[1].__class__, OSError().__class__):
                raise answer[1]

            else:
                # The branch is not used here, but maybe it'll help someone ;)
                return answer[1]

        else:
            # Call the specified method with the arguments passed to the mock.
            return answer[1](*args, **kwargs)

# --------------------------------------------------------------------------------


class TestLAN_IPEntry_Manual(unittest.TestCase):
    def setUp(self):
        # This temporary file will act as a standard stream pipe for `Popen`
        self.stdout_mock = tempfile.NamedTemporaryFile(delete=False)

    def tearDown(self):
        # At the end of the test, we'll close and remove the created file
        self.stdout_mock.close()
        os.remove(self.stdout_mock.name)

    @patch('archey.archey.Popen')
    @patch('archey.archey.check_output')
    @patch.dict(
        'archey.archey.config.config',
        {'ip_settings': {'lan_ip_max_count': False}}
    )
    def test_manual_workaround_without_limit(self,
                                             check_output_mock, popen_mock):
        # Our mocks will be "special", please refer to the class above.
        popen_mock.side_effect = FakePopenMock(self.stdout_mock).method
        check_output_mock.side_effect = FakeCheckOutputMock().method
        self.assertEqual(
            LAN_IP().value,
            'XXX.YYY.ZZZ.9, 172.17.0.1, 0123::45:6789:abcd:6817'
        )

    @patch('archey.archey.Popen')
    @patch('archey.archey.check_output')
    @patch.dict(
        'archey.archey.config.config',
        {'ip_settings': {'lan_ip_max_count': 2}}
    )
    def test_manual_workaround_with_limit(self, check_output_mock, popen_mock):
        popen_mock.side_effect = FakePopenMock(self.stdout_mock).method
        check_output_mock.side_effect = FakeCheckOutputMock().method
        self.assertEqual(
            LAN_IP().value,
            'XXX.YYY.ZZZ.9, 172.17.0.1'
        )


if __name__ == '__main__':
    unittest.main()
