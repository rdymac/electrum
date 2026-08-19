# Electrum Ark plugin - arkd REST client
# Copyright (C) 2026 Randy Brito
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Standalone HTTP client for an Arkade operator (arkd).

Talks to the public REST gateway documented by arkd:

* GET /v1/info
* GET /v1/indexer/vtxos

The module has no Electrum imports so it can be unit-tested on its own.
"""

import json
import ssl
from collections import namedtuple
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_SERVERS = (
    ('bitcoin', 'https://arkade.computer'),
    ('signet', 'https://signet.arkade.sh'),
    ('mutinynet', 'https://mutinynet.arkade.sh'),
    ('regtest', 'http://localhost:7070'),
)

DEFAULT_SERVER_URL = 'https://mutinynet.arkade.sh'

USER_AGENT = 'electrum-ark-plugin/0.1'


class ArkClientError(Exception):
    """Raised when the operator cannot be reached or returns invalid data."""


ArkInfo = namedtuple('ArkInfo', [
    'version',
    'network',
    'signer_pubkey',
    'forfeit_pubkey',
    'forfeit_address',
    'session_duration',
    'unilateral_exit_delay',
    'boarding_exit_delay',
    'utxo_min_amount',
    'utxo_max_amount',
    'vtxo_min_amount',
    'vtxo_max_amount',
    'dust',
    'digest',
    'service_status',
])


Vtxo = namedtuple('Vtxo', [
    'txid',
    'vout',
    'amount',
    'script',
    'created_at',
    'expires_at',
    'is_spent',
    'is_swept',
    'is_unrolled',
    'is_preconfirmed',
    'spent_by',
    'ark_txid',
])


def normalize_server_url(url):
    # type: (Optional[str]) -> str
    """Strip whitespace and a trailing slash from an operator URL."""
    if url is None:
        return ''
    text = url.strip()
    if not text:
        return ''
    while text.endswith('/'):
        text = text[:-1]
    return text


def _pick(data, *names, default=None):
    # type: (Dict[str, Any], *str, Any) -> Any
    for name in names:
        if name in data and data[name] not in (None, ''):
            return data[name]
    return default


def _as_int(value, default=0):
    # type: (Any, int) -> int
    if value in (None, ''):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value, default=False):
    # type: (Any, bool) -> bool
    if value in (None, ''):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes')
    return bool(value)


def _as_str(value, default=''):
    # type: (Any, str) -> str
    if value in (None,):
        return default
    return str(value)


def parse_ark_info(payload):
    # type: (Dict[str, Any]) -> ArkInfo
    """Parse GetInfo JSON (camelCase from gRPC-gateway or snake_case)."""
    if not isinstance(payload, dict):
        raise ArkClientError('GetInfo response is not an object')
    status = _pick(payload, 'serviceStatus', 'service_status', default={})
    if status is None:
        status = {}
    return ArkInfo(
        version=_as_str(_pick(payload, 'version', default='')),
        network=_as_str(_pick(payload, 'network', default='')),
        signer_pubkey=_as_str(_pick(payload, 'signerPubkey', 'signer_pubkey', default='')),
        forfeit_pubkey=_as_str(_pick(payload, 'forfeitPubkey', 'forfeit_pubkey', default='')),
        forfeit_address=_as_str(_pick(payload, 'forfeitAddress', 'forfeit_address', default='')),
        session_duration=_as_int(_pick(payload, 'sessionDuration', 'session_duration')),
        unilateral_exit_delay=_as_int(_pick(payload, 'unilateralExitDelay', 'unilateral_exit_delay')),
        boarding_exit_delay=_as_int(_pick(payload, 'boardingExitDelay', 'boarding_exit_delay')),
        utxo_min_amount=_as_int(_pick(payload, 'utxoMinAmount', 'utxo_min_amount')),
        utxo_max_amount=_as_int(_pick(payload, 'utxoMaxAmount', 'utxo_max_amount', default=-1), default=-1),
        vtxo_min_amount=_as_int(_pick(payload, 'vtxoMinAmount', 'vtxo_min_amount')),
        vtxo_max_amount=_as_int(_pick(payload, 'vtxoMaxAmount', 'vtxo_max_amount', default=-1), default=-1),
        dust=_as_int(_pick(payload, 'dust')),
        digest=_as_str(_pick(payload, 'digest', default='')),
        service_status=dict(status) if isinstance(status, dict) else {},
    )


def parse_vtxo(item):
    # type: (Dict[str, Any]) -> Vtxo
    if not isinstance(item, dict):
        raise ArkClientError('VTXO entry is not an object')
    outpoint = _pick(item, 'outpoint', default={}) or {}
    if not isinstance(outpoint, dict):
        outpoint = {}
    return Vtxo(
        txid=_as_str(_pick(outpoint, 'txid', default=_pick(item, 'txid', default=''))),
        vout=_as_int(_pick(outpoint, 'vout', default=_pick(item, 'vout'))),
        amount=_as_int(_pick(item, 'amount')),
        script=_as_str(_pick(item, 'script', default='')),
        created_at=_as_int(_pick(item, 'createdAt', 'created_at')),
        expires_at=_as_int(_pick(item, 'expiresAt', 'expires_at')),
        is_spent=_as_bool(_pick(item, 'isSpent', 'is_spent')),
        is_swept=_as_bool(_pick(item, 'isSwept', 'is_swept')),
        is_unrolled=_as_bool(_pick(item, 'isUnrolled', 'is_unrolled')),
        is_preconfirmed=_as_bool(_pick(item, 'isPreconfirmed', 'is_preconfirmed')),
        spent_by=_as_str(_pick(item, 'spentBy', 'spent_by', default='')),
        ark_txid=_as_str(_pick(item, 'arkTxid', 'ark_txid', default='')),
    )


def parse_vtxos(payload):
    # type: (Dict[str, Any]) -> List[Vtxo]
    if not isinstance(payload, dict):
        raise ArkClientError('GetVtxos response is not an object')
    items = _pick(payload, 'vtxos', default=[])
    if items is None:
        items = []
    if not isinstance(items, list):
        raise ArkClientError('GetVtxos.vtxos is not a list')
    return [parse_vtxo(item) for item in items]


def spendable_balance_sats(vtxos):
    # type: (Iterable[Vtxo]) -> int
    total = 0
    for vtxo in vtxos:
        if not vtxo.is_spent and not vtxo.is_swept:
            total += vtxo.amount
    return total


def build_vtxos_query(scripts, spendable_only=False, spent_only=False):
    # type: (Sequence[str], bool, bool) -> List[Tuple[str, str]]
    """Build gRPC-gateway query pairs for GET /v1/indexer/vtxos."""
    params = []  # type: List[Tuple[str, str]]
    for script in scripts:
        text = (script or '').strip()
        if text:
            params.append(('scripts', text))
    if spendable_only:
        params.append(('spendableOnly', 'true'))
    if spent_only:
        params.append(('spentOnly', 'true'))
    return params


def _default_opener(request, timeout):
    # type: (Request, int) -> Any
    context = ssl.create_default_context()
    return urlopen(request, timeout=timeout, context=context)


class ArkClient(object):
    """Minimal arkd REST client."""

    def __init__(self, server_url, timeout=30, opener=None):
        # type: (str, int, Optional[Callable[..., Any]]) -> None
        self.server_url = normalize_server_url(server_url)
        if not self.server_url:
            raise ArkClientError('Ark server URL is empty')
        self.timeout = timeout
        self._opener = opener or _default_opener

    def _url(self, path, query=None):
        # type: (str, Optional[Sequence[Tuple[str, str]]]) -> str
        url = self.server_url + path
        if query:
            url = url + '?' + urlencode(query)
        return url

    def _request(self, path, query=None):
        # type: (str, Optional[Sequence[Tuple[str, str]]]) -> Dict[str, Any]
        url = self._url(path, query)
        request = Request(url, headers={
            'Accept': 'application/json',
            'User-Agent': USER_AGENT,
        })
        try:
            response = self._opener(request, self.timeout)
            try:
                raw = response.read()
            finally:
                try:
                    response.close()
                except Exception:
                    pass
        except HTTPError as e:
            body = ''
            try:
                body = e.read().decode('utf-8', 'replace')
            except Exception:
                pass
            raise ArkClientError('HTTP %s from %s: %s' % (e.code, url, body[:300]))
        except URLError as e:
            raise ArkClientError('Failed to reach %s: %s' % (url, e.reason))
        except Exception as e:
            raise ArkClientError('Failed to reach %s: %s' % (url, e))
        try:
            payload = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError) as e:
            raise ArkClientError('Invalid JSON from %s: %s' % (url, e))
        if not isinstance(payload, dict):
            raise ArkClientError('JSON from %s is not an object' % url)
        return payload

    def get_info(self):
        # type: () -> ArkInfo
        return parse_ark_info(self._request('/v1/info'))

    def get_vtxos(self, scripts, spendable_only=False, spent_only=False):
        # type: (Sequence[str], bool, bool) -> List[Vtxo]
        cleaned = [s.strip() for s in scripts if s and s.strip()]
        if not cleaned:
            raise ArkClientError('At least one VTXO script is required')
        query = build_vtxos_query(cleaned, spendable_only=spendable_only, spent_only=spent_only)
        return parse_vtxos(self._request('/v1/indexer/vtxos', query))
