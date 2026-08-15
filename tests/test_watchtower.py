import asyncio
from contextlib import asynccontextmanager
from unittest import mock

from electrum.util import JsonRPCError

from . import ElectrumTestCase


class TestWatchtowerSync(ElectrumTestCase):
    TESTNET = True

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.lnwallet = self.create_mock_lnwallet(name='watchtower_wallet')
        self.lnwallet.watchtower_ctns = {}

    def _fake_channel(self, outpoint: str, *, current_ctn: int = 5):
        chan = mock.Mock()
        chan.channel_id = outpoint.encode()
        chan.funding_outpoint.to_str.return_value = outpoint
        chan.get_funding_address.return_value = 'tb1qwatchtower'
        chan.get_oldest_unrevoked_ctn.return_value = current_ctn
        chan.create_sweeptxs_for_watchtower.return_value = []
        return chan

    def _fake_watchtower(self, ctn):
        watchtower = mock.Mock()
        watchtower.get_ctn = mock.AsyncMock(return_value=ctn)
        watchtower.add_sweep_tx = mock.AsyncMock()
        watchtower.add_method = mock.Mock()
        return watchtower

    async def _run_sync_loop(self, *, fake_sync, cancel_after_sleeps: int):
        sleep_calls = 0

        async def fake_sleep(_seconds):
            nonlocal sleep_calls
            sleep_calls += 1
            if sleep_calls >= cancel_after_sleeps:
                raise asyncio.CancelledError()

        @asynccontextmanager
        async def fake_session(*args, **kwargs):
            yield mock.Mock()

        with (
            mock.patch.object(self.lnwallet, 'sync_channel_with_watchtower', side_effect=fake_sync),
            mock.patch('electrum.lnworker.make_aiohttp_session', fake_session),
            mock.patch('electrum.lnworker.JsonRPCClient', return_value=self._fake_watchtower(0)),
            mock.patch('electrum.lnworker.asyncio.sleep', fake_sleep),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await self.lnwallet.sync_with_remote_watchtower()

    async def test_invalid_get_ctn_is_ignored(self):
        chan = self._fake_channel('aa' * 32 + ':0')
        for ctn in (-2, -1, None, True, 1.5, 'Error: 500'):
            with self.subTest(ctn=ctn):
                chan.create_sweeptxs_for_watchtower.reset_mock()
                watchtower = self._fake_watchtower(ctn)
                await self.lnwallet.sync_channel_with_watchtower(chan, watchtower)
                chan.create_sweeptxs_for_watchtower.assert_not_called()
                watchtower.add_sweep_tx.assert_not_called()
                self.assertNotIn(chan.funding_outpoint.to_str(), self.lnwallet.watchtower_ctns)

    async def test_valid_get_ctn_uploads_missing_sweep_txs(self):
        chan = self._fake_channel('bb' * 32 + ':0', current_ctn=5)
        watchtower = self._fake_watchtower(1)
        await self.lnwallet.sync_channel_with_watchtower(chan, watchtower)
        chan.create_sweeptxs_for_watchtower.assert_has_calls([mock.call(2), mock.call(3), mock.call(4)])
        self.assertEqual(self.lnwallet.watchtower_ctns[chan.funding_outpoint.to_str()], 4)

    async def test_one_channel_failure_does_not_skip_the_rest(self):
        chan_bad = self._fake_channel('cc' * 32 + ':0')
        chan_good = self._fake_channel('dd' * 32 + ':0')
        self.lnwallet._channels[chan_bad.channel_id] = chan_bad
        self.lnwallet._channels[chan_good.channel_id] = chan_good
        self.lnwallet.config.WATCHTOWER_CLIENT_URL = 'https://watchtower.example/rpc'
        synced = []

        async def fake_sync(chan, watchtower):
            synced.append(chan)
            if chan is chan_bad:
                raise AssertionError(-2)

        await self._run_sync_loop(fake_sync=fake_sync, cancel_after_sleeps=2)
        self.assertEqual(synced, [chan_bad, chan_good])

    async def test_jsonrpc_error_does_not_kill_the_sync_loop(self):
        chan = self._fake_channel('ee' * 32 + ':0')
        self.lnwallet._channels[chan.channel_id] = chan
        self.lnwallet.config.WATCHTOWER_CLIENT_URL = 'https://watchtower.example/rpc'
        iterations = 0

        async def fake_sync(chan, watchtower):
            nonlocal iterations
            iterations += 1
            raise JsonRPCError(code=1, message='boom')

        await self._run_sync_loop(fake_sync=fake_sync, cancel_after_sleeps=3)
        self.assertGreaterEqual(iterations, 2)
