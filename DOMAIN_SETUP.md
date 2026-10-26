# Eazy’s Business AI domain setup

Approved app name: **Eazy’s Business AI**.
Owner-supplied registered domain: **eazysbusinessai.com**.
The earlier spelling EZsBusinessAI.com was corrected by the owner and must not be used.

The application source has been renamed while keeping the existing repository, authentication identities, workflow identifiers, tenant data, conversations and saved drafts. The internal workflow key `vantora_sales` is retained for compatibility; its visible label is now Grow Eazy’s Business AI. Historical saved text is not rewritten. Existing administrator login addresses are account identifiers and remain unchanged.

No domain email inbox is assumed to exist. Public contact and policy pages use the application's contact form rather than displaying the old placeholder Vantora email addresses. Demo-request notifications remain simulated and retain their existing administrator recipient.

## Connection status

The owner chose Netlify for the frontend and approved retaining the existing Emergent backend. The frontend is deployed at https://eazys-business-ai.netlify.app. Both eazysbusinessai.com and www.eazysbusinessai.com are attached to that Netlify project. The approved backend update was released through Emergent's free republish flow.

After owner approval and GoDaddy identity verification, the root A record was changed from Parked to 75.2.60.5 and the www CNAME from eazysbusinessai.com to eazys-business-ai.netlify.app. GoDaddy confirmed each save. Cloudflare and Google public DNS now return the new root target. The other 17 DNS records were compared with the backup and remain unchanged, including Microsoft 365 MX, SPF, DKIM, DMARC, SRV and autodiscovery records. Nameservers remain ns49.domaincontrol.com and ns50.domaincontrol.com.

## Final verification

Netlify has reported successful DNS verification and is provisioning the free HTTPS certificate. Certificate verification and final custom-host checks must pass before claiming that the secure custom domain is live. Some local resolvers still cache the old parked records. Keep TLS verification enabled; do not bypass a browser certificate warning. See NETLIFY_SETUP.md for current launch status and verified behavior.

Domain registration and DNS changes do not create email inboxes or authorize customer-data integrations. No new customer account, paid model call, calendar connection, message delivery or payment was authorized by the hosting setup.
