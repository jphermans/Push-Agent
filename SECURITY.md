# Security Policy

## Supported Versions

This project follows Semantic Versioning. Security fixes are released for the
current major version. Older versions are not maintained.

| Version | Supported          |
|---------|--------------------|
| 1.1.22+ | :white_check_mark: |
| < 1.1.22| :x:                |

The 1.1.22 release includes a forced history rewrite that closed the leak
described below. If you are running any version prior to 1.1.22, upgrade
**and** rotate your Pushover application token — see "Leak Remediation"
below for the exact steps.

## Reporting a Vulnerability

Please open a GitHub issue or pull request on
[Push-Agent](https://github.com/your-username/Push-Agent) with the label
`security`. Do **not** include real credentials, real Pushover tokens, or
real user keys in the report — mask them as `****<last-4-chars>`.

For sensitive reports that should not be public, contact the maintainer
through the GitHub profile listed in `plugin.yaml`'s `author` field
(replace the `TODO` placeholder with your real contact before publishing).

## Leak Remediation (v1.1.19 → v1.1.22)

### What happened

The plugin's local JSON persistence file, `push_zero_config.json`, was
inadvertently committed to the public GitHub repository in two release
commits:

- `v1.1.19` (commit `98e2274`): introduced the file.
- `v1.1.20` (commit `1e45b32`): modified the file.

The file holds plaintext Pushover credentials (a 30-character application
token and a 30-character user/group key) in JSON form. The `.gitignore`
listed the framework mirror (`config.json`) but **not** the local primary
store (`push_zero_config.json`), so `git add -A` captured it.

### What we did

1. **Rotated the leaked Pushover application token** on the Pushover
   dashboard by deleting the affected application and creating a new one.
   The leaked token now returns `HTTP 410 token is invalid` from
   Pushover's API, so any future attempt to use the leaked `(user_key,
   old_token)` pair fails.
2. **Added `push_zero_config.json` to `.gitignore`** so future commits
   ignore the local config file.
3. **`git rm --cached push_zero_config.json`** to untrack the file while
   keeping the local copy on disk for runtime use.
4. **`git filter-repo --invert-paths --path push_zero_config.json`** to
   remove the file from **every commit in history** (not just `HEAD`).
5. **`git push --force origin main`** + **`git push --force origin --tags`**
   to rewrite the public GitHub history and re-publish every tag whose
   SHA changed as a result of the rewrite.

### What you should do if you cloned the repo before the rewrite

If you `git clone`d or `git pull`ed the repository at any point **before**
the 1.1.22 history rewrite, your local clone still contains the leaked
file at the old SHAs. To clean your local clone:

```bash
cd path/to/Push-Agent
git fetch origin
git reset --hard origin/main
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

This drops the orphaned objects from your local object store. Verify
with:

```bash
git log --all -p | grep -c 'asbjz2u2b6mgtkhhsi6wuksoyesmm' || echo 'clean'
```

The expected output is `0` followed by `clean`.

### Residual risk

The Pushover **user/group key** (the 30-char identifier of your Pushover
account or group) is **not** user-rotatable on Pushover's platform.
Pushover does not expose a "regenerate user key" button — to change it,
you must create a brand-new Pushover account.

This is acceptable because Pushover's API requires both `(token, user)`
to authenticate a notification, and the leaked token is now dead. The
leaked user key on its own is just an opaque identifier — it cannot send
notifications without a paired valid application token.

If you want to fully purge the user key from history too, create a new
Pushover account and migrate.

## Lessons Learned

1. **Always include every persistence path in `.gitignore`** — both the
   framework mirror and any plugin-local store.
2. **Prefer the credential-helper pattern only when shell quoting is
   guaranteed safe.** When `set +H` does not reliably disable history
   expansion, fall back to URL-embedded credentials (see the push
   pattern documented in this repo's `plugin.yaml` comments).
3. **Run `git log --all -p | grep` for credential-shaped patterns before
   tagging any release.** This is now part of the release checklist.
4. **Document the user's responsibility clearly.** The Setup page now
   shows the masked form inline (v1.1.14) so users can see that
   something is saved without exposing the plaintext, and `api/save.py`
   has a regex guard that refuses to overwrite real credentials with
   masked input.
