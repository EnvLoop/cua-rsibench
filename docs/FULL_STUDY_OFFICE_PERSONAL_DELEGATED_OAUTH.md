# Self-service delegated Graph tokens for the Office train pilot

**Status: code and fake tests only.** No device login, Microsoft Graph call,
OneDrive access, token acquisition, or Office browser action was performed
for this document. Do not run either login command until the owner and
distinct actor accounts are available and the operator can complete the
Microsoft sign-in. The Mac UI lock and actor-account state remain external
prerequisites.

Microsoft requires an **application (client) ID from an app registration**
before MSAL can start a public-client flow. The operator must register an app
in a Microsoft Entra tenant they control, choose **personal Microsoft
accounts only** (or an audience that includes personal accounts), enable
**Allow public client flows**, and configure Microsoft Graph delegated
`Files.ReadWrite`, `Files.Read`, and `User.Read`. The owner grants the first
and last; the actor grants the second and last. This is a public client:
do not create or provide a client secret. A personal Microsoft account by
itself does not supply an application client ID or app-registration
privileges. The operator must also pin two different expected Graph `/me.id`
values from an independently reviewed account source before enrollment.
The helper will reject a login that resolves to the wrong ID.

The application prerequisites follow [Microsoft's app registration guide](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app),
[public-client configuration](https://learn.microsoft.com/en-us/azure/active-directory/develop/scenario-desktop-app-registration),
and [MSAL Python client documentation](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/client-applications).
Microsoft's [device-code example](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens)
uses `PublicClientApplication.initiate_device_flow` followed by
`acquire_token_by_device_flow`; its [Graph tutorial](https://learn.microsoft.com/en-us/graph/tutorials/powershell)
shows the `consumers` authority for personal-account device authorization.
Microsoft Graph lists delegated personal-account
[`Files.ReadWrite`](https://learn.microsoft.com/en-us/graph/permissions-reference)
and `Files.Read` as available permissions. Actual silent sharing and item
access still require the separate bounded Graph pilot.

Install the optional, pinned local dependency after reviewing the app
registration. `check-config` does not import MSAL or contact Microsoft:

```sh
python3.14 -m pip install -e '.[office_auth]'
PYTHONPATH=.:src python3.14 -m tools.run_office_graph_msal_device_code_v1 \
  --config "$OFFICE_OAUTH_CONFIG" --auth-dir "$OFFICE_AUTH_DIR" check-config
```

`$OFFICE_OAUTH_CONFIG` must be a mode-0600 JSON file under ignored `work/`
with exactly these fields: `schema` =
`cua-office-graph-msal-public-client-v1`, the user's `client_id` GUID,
`authority` = `https://login.microsoftonline.com/consumers`,
`account_audience` = `personal_microsoft_accounts_only` or
`organizations_and_personal_microsoft_accounts`,
`public_client_flows_enabled` = `true`, `role_scopes` =
`{"owner":["Files.ReadWrite","User.Read"],"actor":["Files.Read","User.Read"]}`,
`expected_graph_user_ids` with distinct `owner` and `actor` IDs, and
`max_device_seconds` between 120 and 900. These identifiers and the config
stay private; the CLI reports hashes only.

Once the user is ready, run **each** explicit login in an interactive
terminal. The helper displays only Microsoft's verification URL and a
short-lived device code. The user signs in on Microsoft's page and handles
consent/MFA there; the helper never receives a password or browser cookie.
It requests just the two role scopes, requires the OAuth token response to
state the granted scopes, then calls Graph `/me` to verify the pinned
account ID. It does not access OneDrive at this stage.

```sh
PYTHONPATH=.:src python3.14 -m tools.run_office_graph_msal_device_code_v1 \
  --config "$OFFICE_OAUTH_CONFIG" --auth-dir "$OFFICE_AUTH_DIR" login-owner
PYTHONPATH=.:src python3.14 -m tools.run_office_graph_msal_device_code_v1 \
  --config "$OFFICE_OAUTH_CONFIG" --auth-dir "$OFFICE_AUTH_DIR" login-actor
PYTHONPATH=.:src python3.14 -m tools.run_office_graph_msal_device_code_v1 \
  --config "$OFFICE_OAUTH_CONFIG" --auth-dir "$OFFICE_AUTH_DIR" finalize-scopes
```

Each access token is stored in a distinct mode-0600 file under a mode-0700
role directory; it is **owner-only plaintext at rest**, not encrypted.
This helper does not persist an MSAL refresh token or silently renew expired
access tokens. A role must enroll again in a new private directory when its
token expires. The durable scope receipt contains token SHA-256 fingerprints,
the observed delegated scopes and expiration, **never** bearer values.
Microsoft notes that service access tokens may be opaque or encrypted for
consumer accounts; this helper never parses the Graph access token. It uses
the OAuth response `scope` field and an authenticated Graph `/me` response.
If `scope` is omitted, the helper refuses to create a scope proof rather
than infer authorization from the requested scopes. The [device-code protocol](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code)
documents the returned `scope` field.

To run one explicit train-only Graph bootstrap action without putting bearer
values in shell history or command-line arguments, use the private-token
wrapper. It verifies the two token files against the scope receipt, exposes
them only in the local process environment for that action, then restores the
previous environment. The underlying Graph pilot still performs exact
source/account checks and refuses selection/final files:

```sh
PYTHONPATH=.:src python3.14 -m tools.run_office_graph_pilot_with_private_tokens_v1 \
  --auth-dir "$OFFICE_AUTH_DIR" --spec "$GRAPH_BOOTSTRAP_SPEC" \
  --out "$GRAPH_PILOT_OUT" check
```

Use the same wrapper with `invite`, `delete`, `finalize`, and the explicit
reconciliation or reset-copy commands in the
[train pilot runbook](FULL_STUDY_OFFICE_PERSONAL_GRAPH_BOOTSTRAP_RUNBOOK.md).
It does not automate the separate E2B actor sign-in, browser GUI save,
owner download, or reset. A private token and OAuth scope proof do not by
themselves qualify a model result or release the 20 selection / 100 final
tasks.

Offline fake tests:

```sh
PYTHONPATH=.:src python3.14 -m unittest \
  tests.test_office_graph_msal_device_code_v1 -v
```
