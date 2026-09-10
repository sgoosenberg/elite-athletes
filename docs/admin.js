'use strict';
const endpoint = 'https://azdpgtwltbjhtgnnffil.supabase.co/functions/v1/review-applications';
const login = document.querySelector('#login'), review = document.querySelector('#review');
const message = document.querySelector('#message'), cards = document.querySelector('#cards');
let token = '', applications = [], generation = 0;
function signOut() {
  generation++; token = ''; applications = []; cards.replaceChildren();
  login.hidden = false; review.hidden = true; login.reset();
  message.textContent = 'Signed out. Sign in to review applications.';
}
async function api(path = '', options = {}) {
  const response = await fetch(endpoint + path, {...options, cache: 'no-store', credentials: 'omit', headers: {'Content-Type': 'application/json', ...(token ? {Authorization: `Bearer ${token}`} : {})}});
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) signOut();
    throw new Error(data.error || 'Request failed.');
  }
  return data;
}
login.addEventListener('submit', async event => {
  event.preventDefault(); const button = login.querySelector('button'); button.disabled = true;
  message.textContent = 'Signing in…';
  const form = new FormData(login);
  try {
    const data = await api('?action=login', {method: 'POST', body: JSON.stringify({email: form.get('email'), password: form.get('password')})});
    token = data.access_token; login.reset(); login.hidden = true; review.hidden = false;
    await load();
  } catch (error) {message.textContent = error.message;} finally {button.disabled = false;}
});
async function load() {
  const current = ++generation;
  message.textContent = 'Loading applications…';
  applications = []; cards.replaceChildren();
  try {
    const rows = [];
    for (let offset = 0; ; offset += 100) {
      const data = await api(`?offset=${offset}`);
      if (current !== generation || !token) return;
      rows.push(...data.applications);
      if (data.applications.length < 100) break;
    }
    applications = rows; render(); message.textContent = 'Applications are up to date.';
  } catch (error) {if (current === generation || !token) message.textContent = error.message;}
}
function render() {
  cards.replaceChildren();
  const filter = document.querySelector('#filter').value;
  const rows = applications.filter(row => filter === 'all' || row.status === filter);
  if (!rows.length) {cards.textContent = 'No applications in this section.'; return;}
  for (const row of rows) {
    const card = document.createElement('article');
    for (const [tag, value] of [['h2', row.name], ['p', `Status: ${row.status}`], ['p', `Phone: ${row.phone}`], ['p', row.history || 'No athlete history provided.']]) {
      const element = document.createElement(tag); element.textContent = value; card.append(element);
    }
    try {
      const url = new URL(row.highlights_url);
      if (['https:', 'http:'].includes(url.protocol) && !url.username && !url.password) {
        const link = document.createElement('a'); link.href = url.href; link.textContent = 'View highlights'; link.target = '_blank'; link.rel = 'noopener noreferrer'; card.append(link);
      }
    } catch {}
    for (const [status, label] of [['approved', 'Approve'], ['denied', 'Deny']]) {
      if (status === row.status) continue;
      const button = document.createElement('button'); button.textContent = label;
      button.addEventListener('click', async () => {
        card.querySelectorAll('button').forEach(b => b.disabled = true);
        try {
          await api('', {method: 'POST', body: JSON.stringify({id: row.id, status})});
          if (!token) return;
          row.status = status; render(); message.textContent = `${row.name}: ${status}.`;
        } catch (error) {
          message.textContent = error.message;
          card.querySelectorAll('button').forEach(b => b.disabled = false);
        }
      });
      card.append(button);
    }
    cards.append(card);
  }
}
document.querySelector('#refresh').addEventListener('click', load);
document.querySelector('#logout').addEventListener('click', signOut);
document.querySelector('#filter').addEventListener('change', render);
