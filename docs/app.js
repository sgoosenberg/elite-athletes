'use strict';
const form = document.querySelector('form');
const button = form.querySelector('button');
const notice = document.querySelector('#notice');
let endpoint;
function message(text, error = false) {
  notice.textContent = text;
  notice.className = `notice ${error ? 'error' : 'success'}`;
}
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!endpoint || button.disabled) return;
  button.disabled = true;
  message('Sending your submission…');
  try {
    const response = await fetch(endpoint, {
      method: 'POST', headers: {Accept: 'application/json'},
      credentials: 'omit', body: new URLSearchParams(new FormData(form))
    });
    if (!response.ok) {
      if (response.status === 400) {
        const data = await response.json();
        message(data.error || 'Check your submission and try again.', true);
        return;
      }
      throw new Error('Submission unavailable');
    }
    const data = await response.json();
    if (data.submitted !== true) throw new Error('Unconfirmed submission');
    form.reset();
    message('Application received. Thank you! The organizer will review your submission.');
  } catch {
    message('We could not confirm your submission. It may have saved; contact the organizer before submitting again.', true);
  } finally {
    button.disabled = false;
  }
});
try {
  const url = new URL(window.ELITE_ATHLETES_SUBMIT_URL);
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/functions/v1/smooth-api') throw new Error('Invalid endpoint');
  endpoint = url.href;
  button.disabled = false;
  message('Your name will appear on the public roster if approved. Your phone number and application details stay private.');
} catch {
  message('The form configuration could not load. Please refresh this page or open the live website again.', true);
}

async function loadRoster() {
  const status = document.querySelector('#roster-status');
  const list = document.querySelector('#roster-list');
  try {
    if (!endpoint) throw new Error('Missing endpoint');
    const response = await fetch(endpoint, {credentials: 'omit', cache: 'no-store'});
    if (!response.ok) throw new Error('Roster unavailable');
    const data = await response.json();
    if (!Array.isArray(data.athletes)) throw new Error('Invalid roster');
    const items = data.athletes.map(athlete => {
      const item = document.createElement('li');
      item.textContent = athlete.name;
      return item;
    });
    list.replaceChildren(...items);
    status.textContent = items.length ? '' : 'No approved athletes yet. Check back soon.';
  } catch {
    status.textContent = 'The roster is temporarily unavailable. Please refresh to try again.';
  }
}
loadRoster();
