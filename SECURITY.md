# Security and privacy

This repository is public. Your data is not in it and cannot get into it.

## Where your data lives

Everything personal — profile, saved answers, application history, documents —
is stored in a per-user directory outside this repository:

- Windows: `%LOCALAPPDATA%\ApplyPilot`
- macOS / Linux: `~/.local/share/applypilot`

SQLite holds encrypted blobs. The encryption key is a separate file beside the
database, never a column inside it. A copied database on its own is inert; losing
the key file means losing the profile, which is the intended trade.

`.gitignore` refuses `.env`, `*.key`, `*.sqlite*`, `data/`, `documents/`, `*.docx`
and `*.pdf`. Nothing personal appears in any test, fixture or example.

## The network

The service binds `127.0.0.1` and refuses to bind anything else — passing a
different host is an error, not an option. CORS accepts the extension's own
origin and localhost, nothing more.

The only outbound request the service ever makes is to the model provider, and
only when you have saved a key. Your API key is stored encrypted and is never
read back out: the settings page learns whether a key is set, never what it is.

## Passwords and sign-in

**ApplyPilot does not type passwords.** The browser's own password manager is
the path, and there is no code here that puts a password on a page.

What it does instead: it recognises a sign-in page, tells you which host wants
you signed in, waits, and picks up from whatever the page looks like once you
have. Sign-in is reported as done only when the sign-in form is no longer there.

The authorisation machinery for session-scoped details is built and tested, so
the guard rails exist if that path is ever added. The service holds no secret at
all — it answers one question, *may sign-in details be released for the page in
front of us?*, and answers it strictly:

- the host must match **exactly**, label for label, so `example.com.evil.test`
  gets nothing from an authorisation for `example.com`;
- the page must already have been classified as a sign-in **form**;
- a registration page is refused outright, with a reason;
- the release is single-use and expires.

Sign-in is never reported as successful because a password field is non-empty.
The only evidence that counts is the sign-in form no longer being on the page.

## Boundaries that do not move

- **No account creation.** Creating an account accepts an employer's terms on
  your behalf. On a registration page everything except the credentials is
  filled, leaving you a password and a button.
- **No CAPTCHA, MFA or verification codes.** The invisible reCAPTCHA badge is
  recognised as a badge and does not block anything; an actual challenge is
  handed to you.
- **No fabrication.** Tailoring reorders and rewords records already in your
  profile. There is no code path by which an employer, a date, a degree, a
  metric or a certification can appear that you did not enter.
- **No silent submission.** Final Submit follows the policy you set, and nothing
  is recorded as submitted without an on-page confirmation.
- **No demographic answers** unless you turn that on. Left off, those four
  questions are always handed back to you.

## Erasing everything

Settings → **Erase everything** removes the profile, saved answers, documents and
history from this computer. Delete the key file yourself if you want the
remaining blobs to be unreadable rather than gone.

## Reporting something

Open an issue at <https://github.com/deekshitvegi/applypilot-agent/issues>. Do
not include a profile, a résumé, a database, a key file or a screenshot with
personal details in it.
