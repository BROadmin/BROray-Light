document.addEventListener('DOMContentLoaded', () => {
  const page = location.pathname.split('/').pop() || 'home.html';
  document.querySelectorAll('nav a').forEach(link => {
    const target = (link.getAttribute('href') || '').split(/[?#]/)[0];
    const active = target === page;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
});
