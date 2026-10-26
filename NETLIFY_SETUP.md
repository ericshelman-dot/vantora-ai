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

## Backend release

After explicit owner approval, the prepared backend was republished through Emergent's free republish flow. The platform lists the 2nd publish as `d484c1f`. Production `/api/` now identifies Eazy’s Business AI; both workflow routes exist and require authentication, including through the Netlify proxy. The earlier 404 release gap is resolved.

The pre-existing production administrator session still works. Both workflows were exercised in production using only one new fictional sales prospect and one new fictional customer inquiry in the isolated demo collection; their distinct free drafts were verified. Existing administrator totals remain 23 businesses, 1 active subscription, 21 trialing and $299 estimated MRR. The original demo still has 86 leads and 9 bookings. No existing customer records, calendar events, outbound messages, paid model calls or payments were changed or created by verification. Existing hosting remains on its prior 50-credits/month configuration; the republish control explicitly stated free republishes and no upgrade was selected.

## Custom domain

Both `eazysbusinessai.com` (primary) and `www.eazysbusinessai.com` (redirect to primary) are attached to this Netlify project. Netlify reports Pending DNS verification; a custom-domain HTTPS certificate cannot be provisioned until DNS points to Netlify.

The exact external-DNS targets shown by Netlify are:

| Record | Host | Target |
| --- | --- | --- |
| A | @ | 75.2.60.5 |
| CNAME | www | eazys-business-ai.netlify.app |

Netlify also offers an ALIAS/ANAME apex target `apex-loadbalancer.netlify.com` for providers that support it. Use the A fallback above if the current provider does not support apex ALIAS records. Do not set an ordinary CNAME at the apex alongside existing email records.

The owner explicitly approved GoDaddy website-DNS edits. All 19 current DNS records were backed up before editing. GoDaddy's identity-verification process stalled after an owner-provided SMS code was submitted, and its recovery route requires a fresh user sign-in. No completed DNS save has been confirmed; public apex records still return 15.197.148.33 and 3.33.130.190. The DNS task remains pending that sign-in. After it completes, update only the two approved website records, compare all remaining MX/TXT/DKIM/SRV/NS records against the backup, then verify propagation and HTTPS. Do not transfer nameservers or buy email/hosting add-ons. The verification code is not stored in project files.
