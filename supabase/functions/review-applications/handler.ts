const ADMIN_EMAIL = 'sgoosenberg@gmail.com';
export function makeHandler(env: (key: string) => string | undefined, request = fetch) {
  return async (req: Request) => {
    const headers = new Headers({'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Vary': 'Origin'});
    const reply = (status: number, body: object) => new Response(JSON.stringify(body), {status, headers});
    const origin = env('PUBLIC_ORIGIN');
    if (!origin || req.headers.get('origin') !== origin) return reply(403, {error: 'Origin not allowed.'});
    headers.set('Access-Control-Allow-Origin', origin);
    headers.set('Access-Control-Allow-Headers', 'authorization, content-type');
    headers.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    if (req.method === 'OPTIONS') return reply(200, {});
    if (!['GET', 'POST'].includes(req.method)) return reply(405, {error: 'Method not allowed.'});
    try {
      const project = env('SUPABASE_URL');
      const key = env('SUPABASE_SERVICE_ROLE_KEY');
      if (!project || !key) return reply(503, {error: 'Review service unavailable.'});
      const auth: Record<string, string> = {apikey: key, 'Content-Type': 'application/json'};
      if (!key.startsWith('sb_secret_')) auth.Authorization = `Bearer ${key}`;
      const url = new URL(req.url);
      if (req.method === 'POST' && url.searchParams.get('action') === 'login') {
        const body = await readBody(req);
        if (String(body.email).toLowerCase() !== ADMIN_EMAIL || typeof body.password !== 'string') return reply(401, {error: 'Sign-in failed. Check your email and password.'});
        const result = await request(`${project}/auth/v1/token?grant_type=password`, {
          method: 'POST', headers: {apikey: env('SUPABASE_ANON_KEY') || key, 'Content-Type': 'application/json'},
          body: JSON.stringify({email: ADMIN_EMAIL, password: body.password}),
        });
        if (!result.ok) return reply(401, {error: 'Sign-in failed. Check your email and password.'});
        const session = await result.json();
        if (!allowed(session.user)) return reply(403, {error: 'Administrator access required.'});
        return reply(200, {access_token: session.access_token});
      }
      const authorization = req.headers.get('authorization');
      if (!authorization?.startsWith('Bearer ')) return reply(401, {error: 'Please sign in.'});
      const identity = await request(`${project}/auth/v1/user`, {headers: {apikey: key, Authorization: authorization}});
      if (!identity.ok) return reply(401, {error: 'Session expired. Please sign in again.'});
      if (!allowed(await identity.json())) return reply(403, {error: 'Administrator access required.'});
      if (req.method === 'GET') {
        const offset = Number(url.searchParams.get('offset') || 0);
        if (!Number.isSafeInteger(offset) || offset < 0) return reply(400, {error: 'Invalid page.'});
        const result = await request(`${project}/rest/v1/athlete_submissions?select=id,name,phone,history,highlights_url,status,created_at&order=created_at.desc,id.asc&limit=100&offset=${offset}`, {headers: auth});
        if (!result.ok) throw new Error('Storage error');
        return reply(200, {applications: await result.json()});
      }
      const body = await readBody(req);
      if (typeof body.id !== 'string' || !body.id || body.id.length > 200 || !['approved', 'denied'].includes(body.status)) return reply(400, {error: 'Invalid decision.'});
      const result = await request(`${project}/rest/v1/athlete_submissions?id=eq.${encodeURIComponent(body.id)}&select=id,status`, {
        method: 'PATCH', headers: {...auth, Prefer: 'return=representation'}, body: JSON.stringify({status: body.status}),
      });
      if (!result.ok) throw new Error('Storage error');
      const rows = await result.json();
      return rows.length === 1 ? reply(200, {updated: true}) : reply(404, {error: 'Application not found.'});
    } catch {
      return reply(503, {error: 'Could not complete the request. Refresh before retrying a decision.'});
    }
  };
}
function allowed(user: {email?: string; email_confirmed_at?: string; is_anonymous?: boolean}) {
  return user?.email?.toLowerCase() === ADMIN_EMAIL && !!user.email_confirmed_at && !user.is_anonymous;
}
async function readBody(req: Request) {
  if (!req.headers.get('content-type')?.startsWith('application/json')) throw new Error('Invalid content type');
  const reader = req.body?.getReader();
  if (!reader) throw new Error('Missing body');
  const chunks = []; let size = 0;
  for (;;) {
    const {value, done} = await reader.read();
    if (done) break;
    size += value.length;
    if (size > 4096) {await reader.cancel(); throw new Error('Body too large');}
    chunks.push(value);
  }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) {bytes.set(chunk, offset); offset += chunk.length;}
  return JSON.parse(new TextDecoder().decode(bytes));
}
