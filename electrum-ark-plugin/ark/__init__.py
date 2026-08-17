try:
    from electrum.i18n import _
except ImportError:  # standalone tests / docs
    def _(text):
        return text

fullname = _('Ark')
description = ' '.join([
    _("Connect Electrum to an Arkade operator (arkd) over the public REST API."),
    _("Inspect server parameters, look up VTXOs, and prepare boarding and off-chain sends."),
])
available_for = ['qt', 'cmdline']
