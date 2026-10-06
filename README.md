# grokforge

xAI (Grok) auto-register and auto-connect to [9router](http://localhost:20128), using headless Camoufox and curl_cffi. Temp mail is pluggable: the default provider is [Tempik](https://tempik.neroism.web.id/), but any other provider can be added in a few lines.

![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

---

## Features

- Fully automatic registration on `accounts.x.ai`, including OTP verification
- Pluggable temp mail: swap Tempik for another service via `TEMPMAIL_PROVIDER`
- Four-layer OTP detection: `data-otp` attribute, subject pattern, banner element, generic fallback
- Automatic 9router login with disk and memory token caching
- OAuth device-code flow with multi-variant approve and backoff-aware polling
- Headless Camoufox with Chrome 136 fingerprint
- Multi-threaded batch execution with locking and barrier synchronization
- Detailed debug trace with `[dbg]` markers at every step
- Automatic screenshot capture on failure (`fail_<username>.png`)

---

## Requirements

- Python 3.10 or later
- A running 9router instance (default: `http://localhost:20128`)
- Stable internet connection for xAI and the chosen temp mail provider

---

## Installation

```bash
git clone https://github.com/Daxxiee0x1/grokforge.git
cd grokforge

python -m venv venv
source venv/bin/activate     # Linux / macOS
# venv\Scripts\activate      # Windows

pip install -r requirements.txt
```

Camoufox will automatically download a Firefox fork on first run (approximately 200 MB).

---

## Configuration

Copy `.env.example` to `.env` and adjust as needed:

```bash
cp .env.example .env
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TEMPMAIL_PROVIDER` | `tempik` | Which temp mail provider to use |
| `TEMPIK_BASE` | `https://tempik.neroism.web.id` | Tempik base URL |
| `TEMPIK_DOMAINS` | `neroism.web.id` | Comma-separated list of Tempik email domains |
| `TEMPIK_DEBUG` | `0` | Set to `1` to dump the inbox HTML to disk |
| `DEFAULT_PASSWORD` | `LauSapeEmpruy88@@` | Password used for new xAI accounts |
| `ROUTER_BASE` | `http://localhost:20128` | 9router base URL |
| `ROUTER_PASSWORD` | `123456` | 9router UI password used for auto-login |
| `ROUTER_AUTH_TOKEN` | (empty) | Optional. If empty, auto-login is used |
| `ROUTER_TOKEN_FILE` | `.9router_token.json` | Path to the disk cache for the token |
| `DEFAULT_THREADS` | `1` | Default number of concurrent threads |

---

## Temp Mail Providers

The temp mail backend is selectable via `TEMPMAIL_PROVIDER`. The choice is read from `.env` at startup and has no impact on the rest of the flow.

### Available Providers

| Name | Notes |
|---|---|
| `tempik` | Default. Server-side rendered inbox. Works out of the box. |

### Switching Provider

Edit `.env`:

```env
TEMPMAIL_PROVIDER=tempik
```

The rest of the pipeline (`xai.py`, `router.py`) does not need any change.

### Adding a Custom Provider

1. Create a new file at `grokforge/tempmail/providers/<name>.py`.

2. Subclass `BaseTempMail` and register with the decorator:

   ```python
   from .. import register
   from ..base import BaseTempMail

   @register("myprovider")
   class MyProvider(BaseTempMail):
       def __init__(self, email: str | None = None):
           if email is None:
               email = "random-user@example.com"
           super().__init__(email)
           # ... provider-specific init ...

       def create_inbox(self) -> bool:
           # Register the inbox with the provider's API.
           ...

       def wait_code(self, retries=20, delay=3, since_ts=None) -> str | None:
           # Poll the inbox until an OTP is found.
           ...
   ```

3. Import the module so the decorator runs:

   ```python
   # grokforge/tempmail/providers/__init__.py
   from . import tempik     # noqa: F401
   from . import myprovider # noqa: F401
   ```

4. Set `TEMPMAIL_PROVIDER=myprovider` in `.env`.

The provider only needs to implement two methods:

- `create_inbox() -> bool`
- `wait_code(retries, delay, since_ts) -> str | None`

Any provider-specific configuration can be read directly with `os.getenv(...)` inside the provider module.

---

## Usage

```bash
python main.py
```

The script will prompt for:

```
? How many accounts? 5
? Threads? [1] 3
? Proxy? (y/n) n
```

### Flow

1. Auto-login to 9router: check disk cache, then API login, then Camoufox fallback.
2. Create an inbox using the chosen temp mail provider.
3. Launch Camoufox headless, open `accounts.x.ai/sign-up`.
4. Fill in the email, wait for the OTP in the inbox, submit the OTP.
5. Fill in the password and name.
6. Wait for the `sso` cookie. If it is missing, retry login using the newly created credentials.
7. Extract the user id from the JWT in the `sso` cookie.
8. Connect to 9router via device-code OAuth:
   - Fetch a device code.
   - Warm the consent page and extract hidden fields (`consent_token`, `castle_request_token`).
   - Verify the user code.
   - Approve using multiple body variants.
   - Poll until `success: true`.
9. Persist the credentials to `accounts.txt`.

### Sample Output

```
[#1] >> c97wd4xfi6fq@neroism.web.id - Melati Pasaribu
[#1]  [1/5] signup...
[#1]  [2/5] email sent
[#1]  [3/5] OTP 742271
[#1]  [OK] account OK
[#1]  [4/5] uid=b6b370e0-c531-4be3-961f-acff53016f8a
  [+] Connect 9router...
  [OK] 9router connected
[#1]  [5/5] saved -> accounts.txt
```

Format of `accounts.txt`:

```
email|password|name|uid|router=connected|timestamp
```

---

## Project Structure

```
grokforge/
├── main.py                          # CLI entry point
├── grokforge/
│   ├── __init__.py
│   ├── colors.py                    # ANSI color helpers
│   ├── config.py                    # .env loader and constants
│   ├── utils.py                     # random_username, extract_uid, session helpers
│   ├── router.py                    # 9router auto-login and connect flow
│   ├── xai.py                       # register_one()
│   └── tempmail/
│       ├── __init__.py              # provider registry and factory
│       ├── base.py                  # BaseTempMail abstract class
│       └── providers/
│           ├── __init__.py
│           └── tempik.py            # Tempik implementation
└── tests/
    └── test_tempik.py               # OTP extraction unit tests
```

---

## Testing

```bash
python -m pytest tests/ -v
# or without pytest:
python tests/test_tempik.py
```

The tests do not require internet access; they replay a captured HTML fixture.

---

## Troubleshooting

### `Unknown temp mail provider`

The value of `TEMPMAIL_PROVIDER` is not registered. Check spelling and make sure the provider module is imported in `grokforge/tempmail/providers/__init__.py`.

### `ROUTER_AUTH_TOKEN expired` or HTTP 401

The script refreshes the token automatically via `ROUTER_PASSWORD`. If the problem persists:

- Verify 9router is reachable: `curl http://localhost:20128`
- Confirm the password in `.env` is correct
- Delete the cached token: `rm .9router_token.json`

### `sso still missing` or `uid=-`

Signup did not authenticate correctly. Inspect `fail_<username>.png` to see what the browser was showing. Common causes:

- xAI rate-limited the IP. Use a proxy.
- The signup form structure changed. Update selectors in `xai.py`.

### OTP timeout

- Set `TEMPIK_DEBUG=1` (or the equivalent for your provider) to dump the inbox HTML.
- Inspect `tempik_debug_<username>.html` to check whether the email arrived.

### `HTTP 503 / 426: Grok CLI version outdated` (in 9router)

Update 9router to the latest version, or override the header `x-grok-client-version: 1.0.44` from the 9router dashboard.

---

## Contributing

Pull requests are welcome. For larger changes, please open an issue first to discuss the proposed change.

```bash
git checkout -b feature/your-feature
git commit -m "Add your feature"
git push origin feature/your-feature
```

---

## Disclaimer

This project is provided for educational and research purposes only. Use it at your own risk. The author is not responsible for any misuse, including violations of the Terms of Service of xAI or any other service involved.

---

## License

[MIT](LICENSE)