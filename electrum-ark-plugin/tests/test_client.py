import json
import os
import sys
import unittest
from io import BytesIO
from urllib.error import HTTPError, URLError

HERE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from ark.client import (  # noqa: E402
    ArkClient,
    ArkClientError,
    build_vtxos_query,
    normalize_server_url,
    parse_ark_info,
    parse_vtxos,
    spendable_balance_sats,
)


INFO_CAMEL = {
    'version': '1.2.3',
    'network': 'mutinynet',
    'signerPubkey': 'aa' * 32,
    'forfeitPubkey': 'bb' * 32,
    'forfeitAddress': 'tb1qforfeit',
    'sessionDuration': '30',
    'unilateralExitDelay': 512,
    'boardingExitDelay': 1024,
    'utxoMinAmount': 330,
    'utxoMaxAmount': -1,
    'vtxoMinAmount': 1,
    'vtxoMaxAmount': -1,
    'dust': '330',
    'digest': 'deadbeef',
    'serviceStatus': {'ark': 'ok', 'indexer': 'ok'},
}

INFO_SNAKE = {
    'version': '9.9.9',
    'network': 'bitcoin',
    'signer_pubkey': 'cc' * 32,
    'forfeit_pubkey': 'dd' * 32,
    'forfeit_address': 'bc1qforfeit',
    'session_duration': 60,
    'unilateral_exit_delay': 144,
    'boarding_exit_delay': 288,
    'utxo_min_amount': 546,
    'utxo_max_amount': 0,
    'vtxo_min_amount': 10,
    'vtxo_max_amount': 100000,
    'dust': 546,
    'digest': 'cafebabe',
    'service_status': {'ark': 'degraded'},
}

VTXOS_PAYLOAD = {
    'vtxos': [
        {
            'outpoint': {'txid': '11' * 32, 'vout': 0},
            'amount': '1500',
            'script': '5120ab',
            'createdAt': 100,
            'expiresAt': 200,
            'isSpent': False,
            'isSwept': False,
            'isUnrolled': False,
            'isPreconfirmed': True,
        },
        {
            'outpoint': {'txid': '22' * 32, 'vout': 1},
            'amount': 700,
            'script': '5120cd',
            'is_spent': True,
            'spent_by': '33' * 32,
        },
        {
            'outpoint': {'txid': '44' * 32, 'vout': 2},
            'amount': 200,
            'script': '5120ef',
            'isSwept': True,
        },
    ]
}


class FakeResponse(object):
    def __init__(self, payload, status=200):
        self._buf = BytesIO(json.dumps(payload).encode('utf-8'))
        self.status = status

    def read(self):
        return self._buf.read()

    def close(self):
        return None


class TestNormalizeUrl(unittest.TestCase):

    def test_strips_slash_and_space(self):
        self.assertEqual(
            normalize_server_url(' https://mutinynet.arkade.sh/ '),
            'https://mutinynet.arkade.sh')

    def test_empty(self):
        self.assertEqual(normalize_server_url(None), '')
        self.assertEqual(normalize_server_url('   '), '')


class TestParseInfo(unittest.TestCase):

    def test_camel_case(self):
        info = parse_ark_info(INFO_CAMEL)
        self.assertEqual(info.version, '1.2.3')
        self.assertEqual(info.network, 'mutinynet')
        self.assertEqual(info.signer_pubkey, 'aa' * 32)
        self.assertEqual(info.forfeit_address, 'tb1qforfeit')
        self.assertEqual(info.session_duration, 30)
        self.assertEqual(info.dust, 330)
        self.assertEqual(info.utxo_max_amount, -1)
        self.assertEqual(info.service_status['ark'], 'ok')

    def test_snake_case(self):
        info = parse_ark_info(INFO_SNAKE)
        self.assertEqual(info.version, '9.9.9')
        self.assertEqual(info.network, 'bitcoin')
        self.assertEqual(info.utxo_max_amount, 0)
        self.assertEqual(info.vtxo_max_amount, 100000)
        self.assertEqual(info.service_status['ark'], 'degraded')

    def test_rejects_non_object(self):
        with self.assertRaises(ArkClientError):
            parse_ark_info(['nope'])


class TestParseVtxos(unittest.TestCase):

    def test_balance_ignores_spent_and_swept(self):
        vtxos = parse_vtxos(VTXOS_PAYLOAD)
        self.assertEqual(len(vtxos), 3)
        self.assertEqual(vtxos[0].txid, '11' * 32)
        self.assertTrue(vtxos[0].is_preconfirmed)
        self.assertTrue(vtxos[1].is_spent)
        self.assertEqual(spendable_balance_sats(vtxos), 1500)

    def test_empty_list(self):
        self.assertEqual(parse_vtxos({'vtxos': []}), [])
        self.assertEqual(parse_vtxos({}), [])


class TestQuery(unittest.TestCase):

    def test_repeated_scripts_and_flags(self):
        query = build_vtxos_query(['  a ', '', 'b'], spendable_only=True)
        self.assertEqual(query, [
            ('scripts', 'a'),
            ('scripts', 'b'),
            ('spendableOnly', 'true'),
        ])


class TestClient(unittest.TestCase):

    def test_get_info(self):
        def opener(request, timeout):
            self.assertTrue(request.full_url.endswith('/v1/info'))
            self.assertEqual(timeout, 5)
            return FakeResponse(INFO_CAMEL)

        client = ArkClient('https://mutinynet.arkade.sh/', timeout=5, opener=opener)
        info = client.get_info()
        self.assertEqual(info.network, 'mutinynet')
        self.assertEqual(client.server_url, 'https://mutinynet.arkade.sh')

    def test_get_vtxos(self):
        seen = {}

        def opener(request, timeout):
            seen['url'] = request.full_url
            return FakeResponse(VTXOS_PAYLOAD)

        client = ArkClient('https://example.test', opener=opener)
        vtxos = client.get_vtxos(['5120ab'], spendable_only=True)
        self.assertIn('scripts=5120ab', seen['url'])
        self.assertIn('spendableOnly=true', seen['url'])
        self.assertEqual(spendable_balance_sats(vtxos), 1500)

    def test_http_error(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 503, 'down', hdrs=None, fp=BytesIO(b'busy'))

        client = ArkClient('https://example.test', opener=opener)
        with self.assertRaises(ArkClientError) as ctx:
            client.get_info()
        self.assertIn('503', str(ctx.exception))

    def test_url_error(self):
        def opener(request, timeout):
            raise URLError('no route')

        client = ArkClient('https://example.test', opener=opener)
        with self.assertRaises(ArkClientError):
            client.get_info()

    def test_empty_url(self):
        with self.assertRaises(ArkClientError):
            ArkClient('   ')

    def test_vtxos_require_script(self):
        client = ArkClient('https://example.test', opener=lambda *a: FakeResponse({}))
        with self.assertRaises(ArkClientError):
            client.get_vtxos(['  '])


if __name__ == '__main__':
    unittest.main()
