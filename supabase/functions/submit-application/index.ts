// Public applications and approved names only. Credentials stay on the server.
Deno.serve(async (req: Request) => {
  const origin = Deno.env.get('PUBLIC_ORIGIN');
  const headers = new Headers({'Content-Type': 'application/json', 'Cache-Control': 'no-store'});
  const reply = (status: number, data: object) => new Response(JSON.stringify(data), {status, headers});
  if (!origin) return reply(503, {error: 'Applications are temporarily unavailable.'});
  if (req.headers.get('origin') !== origin) return reply(403, {error: 'Origin not allowed.'});
  headers.set('Access-Control-Allow-Origin', origin);
  headers.set('Vary', 'Origin');
  headers.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  headers.set('Access-Control-Allow-Headers', 'content-type');
  if (req.method === 'OPTIONS') return new Response(null, {status: 204, headers});
  if (req.method === 'GET') {
    try {
      const project = Deno.env.get('SUPABASE_URL');
      const key = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
      if (!project || !key) return reply(503, {error: 'Roster is temporarily unavailable.'});
      const auth: Record<string, string> = {apikey: key};
      if (!key.startsWith('sb_secret_')) auth.Authorization = `Bearer ${key}`;
      const athletes: {name: string}[] = [];
      for (let offset = 0; ; offset += 500) {
        const result = await fetch(`${project}/rest/v1/athlete_submissions?select=name&status=eq.approved&order=name.asc,id.asc&limit=500&offset=${offset}`, {headers: auth});
        if (!result.ok) throw new Error('Roster unavailable');
        const rows = await result.json();
        if (!Array.isArray(rows)) throw new Error('Invalid roster');
        athletes.push(...rows.map(row => ({name: String(row.name)})));
        if (rows.length < 500) break;
      }
      return reply(200, {athletes});
    } catch {
      return reply(503, {error: 'Roster is temporarily unavailable.'});
    }
  }
  if (req.method !== 'POST') return reply(405, {error: 'Method not allowed.'});
  if (!req.headers.get('content-type')?.startsWith('application/x-www-form-urlencoded')) return reply(415, {error: 'Unsupported submission format.'});
  try {
    // Bound actual body size, including requests without Content-Length.
    const reader = req.body?.getReader();
    if (!reader) return reply(400, {error: 'Missing application.'});
    const chunks: Uint8Array[] = [];
    let size = 0;
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      size += value.length;
      if (size > 20000) { await reader.cancel(); return reply(413, {error: 'Application too large.'}); }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    const form = new URLSearchParams(new TextDecoder('utf-8', {fatal: true}).decode(bytes));
    const name = (form.get('name') || '').trim();
    const phone = (form.get('phone') || '').trim();
    const history = (form.get('history') || '').trim();
    const highlights_url = (form.get('highlights_url') || '').trim();
    if (!name || name.length > 80 || !phone || phone.length > 30 || history.length > 2000 || highlights_url.length > 2000) return reply(400, {error: 'Enter a name (up to 80 characters), phone (up to 30), and history (up to 2,000).'});
    if (highlights_url) {
      try {
        const url = new URL(highlights_url);
        if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) throw new Error();
      } catch { return reply(400, {error: 'Enter a valid http:// or https:// highlights link.'}); }
    }
    const project = Deno.env.get('SUPABASE_URL');
    const key = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
    if (!project || !key) return reply(503, {error: 'Applications are temporarily unavailable.'});
    const auth: Record<string, string> = {'apikey': key, 'Content-Type': 'application/json', 'Prefer': 'return=minimal'};
    if (!key.startsWith('sb_secret_')) auth.Authorization = `Bearer ${key}`;
    const saved = await fetch(`${project}/rest/v1/athlete_submissions`, {
      method: 'POST', headers: auth,
      body: JSON.stringify({id: crypto.randomUUID(), name, phone, history, highlights_url, status: 'pending'}),
    });
    if (!saved.ok) return reply(503, {error: 'Could not confirm submission. Please contact the organizer before retrying.'});
    return reply(201, {submitted: true});
  } catch {
    return reply(503, {error: 'Could not confirm submission. Please contact the organizer before retrying.'});
  }
});
