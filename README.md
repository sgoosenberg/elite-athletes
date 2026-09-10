# Elite Athletes

The public website is an application form only. Applications are stored in Supabase;
review and approval run in a Python dashboard bound to 127.0.0.1 on your Mac.
There is no public roster or hosted admin dashboard.

## Pieces

- `docs/`: the only public website artifact. No admin code or secrets.
- `supabase/functions/submit-application/`: an anonymous POST endpoint that validates
  fields and inserts pending applications. It cannot list applicants or approve them.
- `supabase_setup.sql`: existing `athlete_submissions` schema with Row Level Security
  and no anonymous/authenticated table privileges. Existing records are preserved.
  Statuses remain pending/approved/denied for compatibility with saved applications.
- `local_admin/run.py`, `portal.py`, `cloud_store.py`: Mac-only dashboard and storage
  client. Standard-library Python; no package installation needed. These files stay
  outside the public `docs/` artifact. `hosted.py` is a retired entry point returning
  410 for every request, and `render.yaml` now describes only a static website.

## Supabase setup

The current dashboard deployment is named `smooth-api` in project
`azdpgtwltbjhtgnnffil`. `docs/config.js` points to that deployed function;
its source is maintained in `supabase/functions/submit-application/index.ts`.
The function config maps `smooth-api` to that local source file.

1. Run `supabase_setup.sql` in your project's SQL Editor. Keep existing records;
   local `names.json` records are not automatically migrated.
2. In Supabase Edge Function secrets, set `PUBLIC_ORIGIN` to
   `https://sgoosenberg.github.io` (or your actual website origin, without a path).
   The function uses the built-in `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`;
   no manually copied storage key is needed. Never place the secret key in frontend files.
3. With the Supabase CLI authenticated, deploy:
   `supabase functions deploy smooth-api --project-ref azdpgtwltbjhtgnnffil --use-api`.
   The checked-in function config disables JWT verification because applicants
   are anonymous. See [Supabase function configuration](https://supabase.com/docs/guides/functions/function-configuration).
4. Set `window.ELITE_ATHLETES_SUBMIT_URL` in `docs/config.js` to
   `https://azdpgtwltbjhtgnnffil.supabase.co/functions/v1/smooth-api`.

The endpoint limits request size, validates fields, ignores client-supplied IDs and
statuses, and never returns applicant records. Origin checking controls browser
access; it is not bot protection. CAPTCHA/rate limiting is not yet configured.

## Public deployment

### Automatic deployment on commit and push

The workflows in `.github/workflows/` must be pushed before automation is active.
In GitHub Settings > Pages, change Source to **GitHub Actions**.
Create a Supabase personal access token at https://supabase.com/dashboard/account/tokens
and save it as `SUPABASE_ACCESS_TOKEN` in GitHub Settings > Secrets and variables
> Actions > New repository secret. Do not put the token in files or chat.

Push changes to `main` to run tests, rebuild the form, and publish only
`docs/index.html`, `docs/app.js`, and `docs/config.js`. Edit form layout and text
in `portal.py`; generated `docs/index.html` is overwritten by the build.
Changes to `supabase/functions/` or its config also deploy `smooth-api`.
Database migrations and secrets are not changed by these workflows.
Both workflows can be rerun manually from the GitHub Actions tab.

Before the first push, reconcile the GitHub browser commits with the local branch;
do not force-push over them. Include `build_pages.py`, `portal.py`, `cloud_store.py`,
the tests and their supporting modules, `docs/`, `supabase/`, and the workflows.
Keep applicant data and `local_admin/secrets.json` untracked.

### Manual alternative

Publish only `docs/` through GitHub Pages (branch source, `/docs` folder) or the
static-only Render blueprint. No Python process runs in either deployment.
Rebuild the form after design changes with `python3 -B build_pages.py`.
This does not read local applicant files or overwrite `docs/config.js`.

If an old Render Python service already exists, **suspend or delete it** and remove
its stored admin and Supabase credentials. Updating this repository's blueprint
alone does not remove a previously deployed service. These changes have not been
pushed or deployed automatically.

## Run the dashboard on your Mac

1. Copy `local_admin/secrets.example.json` to `local_admin/secrets.json` and fill in
   your Supabase URL and server secret key locally. This file is ignored by Git.
   Do not send the key in chat. Restrict access with
   `chmod 600 local_admin/secrets.json`.
2. Run `python3 local_admin/run.py` from this project folder.
3. Open http://127.0.0.1:8000/elite-athletes-backend.
4. Review applications and click Approve or Deny. Decisions persist in Supabase.
   Stop the dashboard with Ctrl+C when finished.

The server rejects hosted mode and network binding overrides. Review routes check
localhost access and Host headers, and decisions require a random CSRF token.
Do not tunnel or port-forward the dashboard. Supabase data remains online even
when the dashboard is closed. Cloud mode does not create Desktop exports.

`python3 portal.py` retains the legacy local-file workflow for existing `names.json`
data. It also binds only to localhost; use the launcher above for Supabase review.

## Verification

Run `python3 -B -m unittest -v`. Tests cover the form-only public artifact, retired
hosted routes, localhost binding, CSRF, approvals, storage failures and pagination.
The Edge Function requires a Supabase/Deno environment for runtime verification.
After configuration, submit a test application, check it is pending locally, approve
it and verify that the public site still shows only the form. Confirm direct
anonymous table reads/writes are denied and GET on the function returns 405.
