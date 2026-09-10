import {makeHandler} from './handler.ts';
const env = (key: string) => ({PUBLIC_ORIGIN: 'https://sgoosenberg.github.io', SUPABASE_URL: 'https://example.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'test-key'}[key]);
function req(method = 'GET', body?: object, token = true) {
  return new Request('https://example.supabase.co/functions/v1/review-applications', {method, headers: {Origin: 'https://sgoosenberg.github.io', 'Content-Type': 'application/json', ...(token ? {Authorization: 'Bearer user-token'} : {})}, ...(body ? {body: JSON.stringify(body)} : {})});
}
function check(value: unknown) {if (!value) throw new Error('Assertion failed');}
Deno.test('anonymous requests never access storage', async () => {
  const handler = makeHandler(env, (() => {throw new Error('Unexpected fetch');}) as typeof fetch);
  check((await handler(req('GET', undefined, false))).status === 401);
});
for (const user of [{email: 'other@example.com', email_confirmed_at: 'today'}, {email: 'sgoosenberg@gmail.com'}]) {
  Deno.test(`reject unauthorized identity ${JSON.stringify(user)}`, async () => {
    let calls = 0;
    const handler = makeHandler(env, (async () => {calls++; return Response.json(user);}) as typeof fetch);
    check((await handler(req('POST', {id: 'abc', status: 'approved'}))).status === 403);
    check(calls === 1);
  });
}
Deno.test('verified administrator can list and only update status', async () => {
  let calls = 0;
  const handler = makeHandler(env, (async (url, options) => {
    calls++;
    if (String(url).endsWith('/auth/v1/user')) return Response.json({email: 'sgoosenberg@gmail.com', email_confirmed_at: 'today'});
    if (options?.method === 'PATCH') {
      check(options.body === JSON.stringify({status: 'approved'}));
      return Response.json([{id: 'abc', status: 'approved'}]);
    }
    return Response.json([{id: 'abc', status: 'pending'}]);
  }) as typeof fetch);
  check((await handler(req())).status === 200);
  check((await handler(req('POST', {id: 'abc', status: 'approved', phone: 'tampered'}))).status === 200);
  check((await handler(req('POST', {id: 'abc', status: 'invalid'}))).status === 400);
  check(calls === 5);
});
Deno.test('invalid tokens are rejected', async () => {
  const handler = makeHandler(env, (async () => new Response('', {status: 401})) as typeof fetch);
  check((await handler(req())).status === 401);
});
