# Electrum Ark plugin

Standalone Electrum plugin that talks to an [Arkade](https://arkadeos.com) operator (`arkd`) over the public REST API.

This project is **not** inside `electrum/plugins/`. Keep it as its own folder (for example `C:\Users\DELL\Desktop\Cursor\GitHub\electrum-ark-plugin`) and link it into Electrum when you want to load it.

## What it does today

- Connects to a public or local Arkade operator
- Fetches `GET /v1/info` (network, signer key, delays, dust, service status)
- Looks up VTXOs with `GET /v1/indexer/vtxos`
- Qt: **Tools → Ark…** plus a settings panel under **Tools → Plugins**
- Command-line GUI stub so the plugin also loads in `cmdline` mode

Boarding, off-chain sends, and unilateral exits are intentionally not implemented yet. Those need MuSig2 tree signing and BIP-322 intent proofs.

## Default operators

| Network   | URL |
|-----------|-----|
| Bitcoin   | `https://arkade.computer` |
| Signet    | `https://signet.arkade.sh` |
| Mutinynet | `https://mutinynet.arkade.sh` |
| Regtest   | `http://localhost:7070` |

The plugin defaults to Mutinynet so a first run does not touch mainnet.

## Install into Electrum 4.1

Electrum 4.1 only loads plugins from `electrum/plugins/<name>/`. From this folder:

```bash
python link_into_electrum.py --electrum /path/to/electrum
```

On Windows, pointing at your local Electrum checkout:

```bat
python link_into_electrum.py --electrum C:\Users\DELL\Desktop\Cursor\GitHub\electrum
```

That creates a symlink (or directory junction) from `electrum\electrum\plugins\ark` to this project's `ark` package. Then start Electrum and enable **Ark** under **Tools → Plugins**.

Manual link:

```bat
mklink /J C:\Users\DELL\Desktop\Cursor\GitHub\electrum\electrum\plugins\ark C:\Users\DELL\Desktop\Cursor\GitHub\electrum-ark-plugin\ark
```

```bash
ln -s /path/to/electrum-ark-plugin/ark /path/to/electrum/electrum/plugins/ark
```

## Tests

No Electrum install is required for the client tests:

```bash
python -m unittest discover -s tests -v
```

## Layout

```
electrum-ark-plugin/
  ark/           # Electrum plugin package (drop this into electrum/plugins/)
    __init__.py  # plugin metadata
    client.py    # arkd REST client (no Electrum imports)
    ark.py       # shared plugin logic
    qt.py        # Qt GUI
    cmdline.py   # CLI GUI stub
  tests/
  link_into_electrum.py
```
