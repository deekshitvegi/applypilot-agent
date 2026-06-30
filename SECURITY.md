# Security policy

ApplyPilot handles unusually sensitive data: employment history, contact
details, work authorization, demographic answers, resumes, and authenticated
browser sessions.

## Rules

1. Never commit `.env`, candidate data, resumes, cookies, access tokens, or
   passwords.
   If a key is pasted into chat or an issue, revoke it and create a replacement.
2. Do not collect or store LinkedIn or employer credentials. Authentication is
   completed by the user in their own browser.
3. Do not attempt to defeat CAPTCHA, MFA, bot detection, or access controls.
4. Require an explicit user review before an application is submitted.
5. Treat generated resume claims as untrusted until the user confirms them.
6. Use synthetic identities and mock job pages in automated tests.
7. Provider credentials entered in the side panel must travel only to the
   loopback agent, be encrypted at rest, and never be returned by an API.
8. Automatic mode must remain user-enabled, visibly indicated, stoppable, and
   bounded. Login, CAPTCHA, MFA, missing data, and ambiguous submission controls
   always pause automation.

If a secret is committed, revoke it immediately and remove it from repository
history before continuing.
