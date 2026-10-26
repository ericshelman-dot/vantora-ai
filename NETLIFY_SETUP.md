# Eazy’s Business AI on Netlify

The owner chose to retain the existing Emergent backend and database. Netlify hosts the built frontend and proxies `/api/*` to `https://localbiz-9.emergent.host/api/*` before the SPA fallback. Browser API requests stay on the same origin. No database credentials, JWT secrets, model keys, passwords or backend files are shipped in the upload.

## Current deployment

- Netlify project: `eazys-business-ai`
- Site ID: `ca6daa88-23d1-4a97-8e0a-2c468fe37f54`
- Live frontend: https://eazys-business-ai.netlify.app
- Project management: https://app.netlify.com/projects/eazys-business-ai
- Deploy ID: `6ade98afe3c9b6fb2b820178`, state ready, manual production deploy.
- Permanent deploy URL: https://6ade98afe3c9b6fb2b820178--eazys-business-ai.netlify.app

Built locally and uploaded as a static ZIP through the existing signed-in Netlify account. Netlify processed two redirect rules and two header rules successfully. No agent run or plan upgrade was initiated. The current Netlify GitHub installation lists only the Planter Box repository. This project is not connected to Git; future source pushes do not auto-deploy until the owner authorizes access to the app repository. No broader GitHub permissions were requested or granted.

`.netlify/` is ignored so local account/site linkage cannot enter the repository. `netlify.toml` contains the build settings for a future Git connection; `frontend/public/_redirects` and `_headers` are copied into the publish directory for both manual and Git deployments. The publish directory is frontend/build. Explicit REACT_APP_BACKEND_URL settings still support existing hosts; when unset or empty the app uses `/api` on its own origin.

## Verified behavior

The branded homepage, login route and nested dashboard route return the SPA successfully. Public plans load through the proxy and render in the browser. The API root returns the existing production backend response. Anonymous and invalid-session access to `/api/auth/me` returns 401 JSON. Missing API routes remain JSON errors and are not rewritten to index.html.

No new user was registered, no stored customer data was modified, no outbound message or model call was made, and no calendar or payment action was performed. Existing-credential login, Google OAuth and paid chat generation were not exercised. The Netlify proxy has a documented response timeout, so long-running chat streams require additional end-to-end verification before claiming full compatibility.

## Backend release gap

The current production backend is the earlier release: `/api/` identifies Vantora AI and `/api/sales-pilot` returns 404. The new dual-workflow backend is built and tested in the existing Emergent development preview, not released to that production host. Netlify therefore serves the renamed frontend, while the Sales & Marketing page explains that the server needs its workflow update. Do not point production users at the development backend to conceal this gap. Publishing the prepared backend remains a separate owner-approved production step; retain the existing database and secrets.

## Custom domain

Both `eazysbusinessai.com` (primary) and `www.eazysbusinessai.com` (redirect to primary) are attached to this Netlify project. Netlify reports Pending DNS verification; a custom-domain HTTPS certificate cannot be provisioned until DNS points to Netlify.

The exact external-DNS targets shown by Netlify are:

| Record | Host | Target |
| --- | --- | --- |
| A | @ | 75.2.60.5 |
| CNAME | www | eazys-business-ai.netlify.app |

Netlify also offers an ALIAS/ANAME apex target `apex-loadbalancer.netlify.com` for providers that support it. Use the A fallback above if the current provider does not support apex ALIAS records. Do not set an ordinary CNAME at the apex alongside existing email records.

No GoDaddy account was accessed or registrar DNS changed by this task. Existing public apex records still return 15.197.148.33 and 3.33.130.190. Before changing them, obtain explicit owner authorization, review/back up the zone, update only website routing, preserve MX/TXT and all unrelated records, then verify propagation and HTTPS. Do not transfer nameservers or buy email/hosting add-ons. Backend release, registrar access and any additional charge remain subject to the owner's existing explicit-approval boundary.
