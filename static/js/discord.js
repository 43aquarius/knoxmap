// The Discord status switch in the header.
//
// Rich Presence puts what KnoxMap is doing on the player's Discord profile,
// where everyone on their friends list can see it. That is not something to
// turn on for somebody, so the switch starts off and the server only ever
// publishes anything once it has been asked.
//
// The switch hides itself when the build has no Discord application id to
// publish as, rather than offering a control that cannot do anything.
(() => {
  async function start() {
    const wrap = document.getElementById('discordToggle');
    const box = document.getElementById('discordPresence');
    if (!wrap || !box) return;

    let state;
    try {
      state = await (await fetch('/api/discord')).json();
    } catch (_) {
      return;                       // no server, no switch
    }
    if (!state.available) return;   // nothing to publish as

    box.checked = !!state.on;
    wrap.hidden = false;

    box.addEventListener('change', async () => {
      const want = box.checked;
      try {
        const reply = await (await fetch('/api/discord', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ on: want }),
        })).json();
        box.checked = !!reply.on;
      } catch (_) {
        box.checked = !want;        // put it back: nothing was saved
      }
    });
  }

  document.addEventListener('DOMContentLoaded', start);
})();
