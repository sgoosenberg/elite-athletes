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
    message('Application received! The organizer will review your submission.');
  } catch {
    message('We could not confirm your submission. It may have saved; contact the organizer before submitting again.', true);
  } finally {
    button.disabled = false;
  }
});
try {
  const url = new URL(window.ELITE_ATHLETES_SUBMIT_URL);
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/functions/v1/submit-application') throw new Error('Invalid endpoint');
  endpoint = url.href;
  button.disabled = false;
  message('Your application is visible only to the organizer.');
} catch {
  message('Submissions are not open yet. Please check back soon.', true);
}
