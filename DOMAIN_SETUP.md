# Eazy’s Business AI domain setup

Approved app name: **Eazy’s Business AI**.
Owner-supplied registered domain: **eazysbusinessai.com**.
The earlier spelling EZsBusinessAI.com was corrected by the owner and must not be used.

The application source has been renamed while keeping the existing repository, authentication identities, workflow identifiers, tenant data, conversations and saved drafts. The internal workflow key `vantora_sales` is retained for compatibility; its visible label is now Grow Eazy’s Business AI. Historical saved text is not rewritten. Existing administrator login addresses are account identifiers and remain unchanged.

No domain email inbox is assumed to exist. Public contact and policy pages use the application's contact form rather than displaying the old placeholder Vantora email addresses. Demo-request notifications remain simulated and retain their existing administrator recipient.

## Connection status

Public DNS returned nameservers ns49.domaincontrol.com and ns50.domaincontrol.com on October 25, 2026. The apex returned A records 15.197.148.33 and 3.33.130.190. These are observations, not recommended target records. No DNS record, registrar setting, production secret or domain binding was changed.

The new branding is staged in the existing development preview and draft pull request. It has not been published to production or verified on the new domain.

## Steps after owner approval

1. In the existing Localbiz 9 deployment's Custom Domain flow, enter eazysbusinessai.com and obtain the exact platform-provided verification and routing records. Do not reuse the currently observed IP addresses or guess Emergent's targets.
2. Review existing DNS records and export a backup. Preserve email-related MX/TXT records and unrelated hostnames. Apply only the approved records required for this deployment.
3. Add www.eazysbusinessai.com only if desired, and configure a single primary host after checking platform support. Do not assume root and www are automatically configured together.
4. Verify domain ownership and HTTPS. Review the backend URL, credentialed CORS settings, cookies and Google sign-in allowed origins/redirects for the final host without changing existing login identities or passwords.
5. Publish the reviewed build only after explicit production-publish approval. Verify homepage, login, administrator access, both sales workflows, chat widget and policy links over HTTPS on the new host. Use isolated fictional data for any write checks.

Domain connection and production publishing remain pending. Registering a domain does not create email inboxes or authorize customer-data integrations.
