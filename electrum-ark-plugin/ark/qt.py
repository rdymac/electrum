# Electrum Ark plugin - Qt GUI
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

from functools import partial

from PyQt5.QtWidgets import (
    QComboBox, QGridLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QVBoxLayout,
)

from electrum.i18n import _
from electrum.plugin import hook
from electrum.gui.qt.util import (
    Buttons, CancelButton, CloseButton, EnterButton, OkButton, WaitingDialog,
    WindowModalDialog,
)

from .ark import ArkPlugin
from .client import DEFAULT_SERVERS, ArkClientError


class Plugin(ArkPlugin):

    def settings_widget(self, window):
        return EnterButton(_('Settings'), partial(self.settings_dialog, window))

    def settings_dialog(self, window):
        d = WindowModalDialog(window, _('Ark Settings'))
        d.setMinimumWidth(520)
        layout = QVBoxLayout(d)
        grid = QGridLayout()

        grid.addWidget(QLabel(_('Operator preset')), 0, 0)
        preset = QComboBox()
        preset.addItem(_('Custom'), '')
        current = self.get_server_url()
        selected = 0
        for index, (network, url) in enumerate(DEFAULT_SERVERS, start=1):
            preset.addItem('%s — %s' % (network, url), url)
            if url == current:
                selected = index
        preset.setCurrentIndex(selected)
        grid.addWidget(preset, 0, 1)

        grid.addWidget(QLabel(_('Ark server URL')), 1, 0)
        url_edit = QLineEdit()
        url_edit.setText(current)
        grid.addWidget(url_edit, 1, 1)

        def apply_preset(index):
            url = preset.itemData(index)
            if url:
                url_edit.setText(url)

        preset.currentIndexChanged.connect(apply_preset)
        layout.addLayout(grid)
        layout.addWidget(QLabel(_(
            'This plugin talks to an Arkade operator (arkd) over REST. '
            'Boarding and off-chain sends will be added in later revisions.'
        )))
        layout.addLayout(Buttons(CancelButton(d), OkButton(d)))
        if not d.exec_():
            return False
        self.set_server_url(url_edit.text())
        return True

    def show_ark_dialog(self, window):
        d = WindowModalDialog(window, _('Ark'))
        d.setMinimumSize(640, 480)
        layout = QVBoxLayout(d)

        grid = QGridLayout()
        grid.addWidget(QLabel(_('Server')), 0, 0)
        url_edit = QLineEdit()
        url_edit.setText(self.get_server_url())
        grid.addWidget(url_edit, 0, 1)
        layout.addLayout(grid)

        output = QPlainTextEdit()
        output.setReadOnly(True)
        output.setPlaceholderText(_('Server info and VTXO lookup results appear here.'))
        layout.addWidget(output)

        grid2 = QGridLayout()
        grid2.addWidget(QLabel(_('VTXO script (hex)')), 0, 0)
        script_edit = QLineEdit()
        script_edit.setPlaceholderText(_('Taproot / VTXO script hex from the indexer'))
        grid2.addWidget(script_edit, 0, 1)
        layout.addLayout(grid2)

        def show_error(exc_info):
            err = exc_info[1] if exc_info else None
            output.setPlainText(_('Error: {}').format(err or _('unknown error')))

        def on_info(info):
            self.set_server_url(url_edit.text())
            output.setPlainText(self.summarize_info(info))

        def on_vtxos(vtxos):
            self.set_server_url(url_edit.text())
            output.setPlainText(self.summarize_vtxos(vtxos))

        def fetch_info():
            url = url_edit.text()

            def task():
                try:
                    return self.fetch_info(url)
                except ArkClientError:
                    raise

            WaitingDialog(d, _('Contacting Ark server…'), task, on_info, show_error)

        def fetch_vtxos():
            script = script_edit.text().strip()
            if not script:
                output.setPlainText(_('Enter a VTXO script hex first.'))
                return
            url = url_edit.text()

            def task():
                return self.fetch_vtxos([script], spendable_only=False, server_url=url)

            WaitingDialog(d, _('Looking up VTXOs…'), task, on_vtxos, show_error)

        info_btn = QPushButton(_('Get server info'))
        info_btn.clicked.connect(fetch_info)
        vtxo_btn = QPushButton(_('Look up VTXOs'))
        vtxo_btn.clicked.connect(fetch_vtxos)
        layout.addLayout(Buttons(info_btn, vtxo_btn, CloseButton(d)))
        d.exec_()

    @hook
    def init_menubar_tools(self, window, tools_menu):
        tools_menu.addSeparator()
        tools_menu.addAction(_('&Ark…'), partial(self.show_ark_dialog, window))
