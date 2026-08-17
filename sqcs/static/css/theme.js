(function () {
  // Runs synchronously in <head>, before first paint, to avoid a
  // light-mode flash on load for users with a saved/system dark preference.
  var saved = null;
  try { saved = localStorage.getItem('sqcs-theme'); } catch (e) {}
  var theme = saved || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', theme);
})();

function toggleTheme() {
  var html = document.documentElement;
  var next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  try { localStorage.setItem('sqcs-theme', next); } catch (e) {}
}
