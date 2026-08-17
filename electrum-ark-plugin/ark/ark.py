# Electrum Ark plugin
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

from typing import List, Optional, Sequence

from electrum.i18n import _
from electrum.plugin import BasePlugin

from .client import (
    DEFAULT_SERVER_URL,
    ArkClient,
    ArkInfo,
    Vtxo,
    normalize_server_url,
    spendable_balance_sats,
)


CONFIG_SERVER_URL = 'ark_server_url'


class ArkPlugin(BasePlugin):
    """Core Ark plugin: operator URL, REST client, VTXO lookup."""

    def requires_settings(self):
        return True

    def get_server_url(self):
        # type: () -> str
        stored = self.config.get(CONFIG_SERVER_URL)
        url = normalize_server_url(stored)
        return url or DEFAULT_SERVER_URL

    def set_server_url(self, url):
        # type: (str) -> str
        cleaned = normalize_server_url(url)
        self.config.set_key(CONFIG_SERVER_URL, cleaned, True)
        return cleaned

    def make_client(self, server_url=None):
        # type: (Optional[str]) -> ArkClient
        return ArkClient(server_url or self.get_server_url())

    def fetch_info(self, server_url=None):
        # type: (Optional[str]) -> ArkInfo
        return self.make_client(server_url).get_info()

    def fetch_vtxos(self, scripts, spendable_only=True, server_url=None):
        # type: (Sequence[str], bool, Optional[str]) -> List[Vtxo]
        return self.make_client(server_url).get_vtxos(
            scripts, spendable_only=spendable_only)

    def summarize_info(self, info):
        # type: (ArkInfo) -> str
        status_items = []
        for key in sorted(info.service_status.keys()):
            status_items.append('%s=%s' % (key, info.service_status[key]))
        status = ', '.join(status_items) if status_items else _('unknown')
        lines = [
            _('Version: {}').format(info.version or _('unknown')),
            _('Network: {}').format(info.network or _('unknown')),
            _('Signer pubkey: {}').format(info.signer_pubkey or _('unknown')),
            _('Forfeit address: {}').format(info.forfeit_address or _('unknown')),
            _('Session duration: {} s').format(info.session_duration),
            _('Unilateral exit delay: {}').format(info.unilateral_exit_delay),
            _('Boarding exit delay: {}').format(info.boarding_exit_delay),
            _('Dust: {} sats').format(info.dust),
            _('UTXO amount range: {} .. {}').format(info.utxo_min_amount, info.utxo_max_amount),
            _('VTXO amount range: {} .. {}').format(info.vtxo_min_amount, info.vtxo_max_amount),
            _('Service status: {}').format(status),
        ]
        return '\n'.join(lines)

    def summarize_vtxos(self, vtxos):
        # type: (Sequence[Vtxo]) -> str
        spendable = [v for v in vtxos if not v.is_spent and not v.is_swept]
        total = spendable_balance_sats(vtxos)
        lines = [
            _('VTXOs returned: {}').format(len(vtxos)),
            _('Spendable VTXOs: {}').format(len(spendable)),
            _('Spendable balance: {} sats').format(total),
        ]
        preview = vtxos[:20]
        if preview:
            lines.append('')
            lines.append(_('Outpoint | sats | flags'))
            for vtxo in preview:
                flags = []
                if vtxo.is_spent:
                    flags.append('spent')
                if vtxo.is_swept:
                    flags.append('swept')
                if vtxo.is_unrolled:
                    flags.append('unrolled')
                if vtxo.is_preconfirmed:
                    flags.append('preconfirmed')
                flag_text = ','.join(flags) if flags else 'spendable'
                lines.append('%s:%s | %s | %s' % (vtxo.txid, vtxo.vout, vtxo.amount, flag_text))
            if len(vtxos) > len(preview):
                lines.append(_('… and {} more').format(len(vtxos) - len(preview)))
        return '\n'.join(lines)
