/* =============================================
   AMULYA GUPTA PORTFOLIO — main.js
   ============================================= */

// ======= GOOGLE ANALYTICS 4 =======
window.dataLayer = window.dataLayer || [];
function gtag(){ dataLayer.push(arguments); }
gtag('js', new Date());
gtag('config', 'G-M678E1N87E');

// ======= NAV: SCROLL SHADOW + ACTIVE =======
(function(){
  const nav = document.querySelector('.nav');
  const links = document.querySelectorAll('.nav-links a, .nav-mobile a');
  const path = window.location.pathname.split('/').pop() || 'index.html';

  links.forEach(link => {
    const href = link.getAttribute('href') || '';
    if (href === path || (path === '' && href === 'index.html') ||
        (path.includes('index') && href === 'index.html')) {
      link.classList.add('active');
    }
  });

  window.addEventListener('scroll', () => {
    if (nav) nav.classList.toggle('scrolled', window.scrollY > 30);
  });
})();

// ======= HAMBURGER MENU =======
(function(){
  const ham = document.getElementById('hamburger');
  const mobileNav = document.getElementById('nav-mobile');
  if (!ham || !mobileNav) return;
  ham.addEventListener('click', () => {
    ham.classList.toggle('open');
    mobileNav.classList.toggle('open');
  });
})();

// ======= TYPING EFFECT =======
(function(){
  const el = document.getElementById('typing-text');
  if (!el) return;
  const phrases = [
    'MLOps & Python AI Engineer',
    'Production ML Systems Builder',
    'FastAPI + Kubernetes Developer',
    'End-to-End MLOps Specialist',
  ];
  let i = 0, j = 0, deleting = false;
  function type(){
    const phrase = phrases[i];
    el.textContent = deleting ? phrase.slice(0,--j) : phrase.slice(0,++j);
    let delay = deleting ? 45 : 90;
    if (!deleting && j === phrase.length) { delay = 2200; deleting = true; }
    else if (deleting && j === 0) { deleting = false; i = (i+1) % phrases.length; delay = 400; }
    setTimeout(type, delay);
  }
  setTimeout(type, 600);
})();

// ======= STAT COUNTERS =======
(function(){
  const counters = document.querySelectorAll('[data-count]');
  if (!counters.length) return;
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      const target = parseFloat(el.dataset.count);
      const suffix = el.dataset.suffix || '';
      const prefix = el.dataset.prefix || '';
      const isFloat = el.dataset.float === 'true';
      const duration = 1800;
      const steps = 60;
      let current = 0;
      const inc = target / steps;
      const timer = setInterval(() => {
        current = Math.min(current + inc, target);
        el.textContent = prefix + (isFloat ? current.toFixed(1) : Math.floor(current)) + suffix;
        if (current >= target) clearInterval(timer);
      }, duration / steps);
      observer.unobserve(el);
    });
  }, { threshold: 0.5 });
  counters.forEach(c => observer.observe(c));
})();

// ======= FADE-IN ON SCROLL =======
(function(){
  const fades = document.querySelectorAll('.fade-in');
  if (!fades.length) return;
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('visible');
        observer.unobserve(e.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -30px 0px' });
  fades.forEach(el => observer.observe(el));
})();

// ======= GA4 EVENT TRACKING =======
document.addEventListener('click', function(e){
  const btn = e.target.closest('[data-ga-event]');
  if (!btn) return;
  const event = btn.dataset.gaEvent;
  const label = btn.dataset.gaLabel || btn.textContent.trim();
  gtag('event', event, { event_label: label, event_category: 'engagement' });
});

// ======= SMOOTH HASH SCROLL =======
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', function(e){
    const target = document.querySelector(this.getAttribute('href'));
    if (!target) return;
    e.preventDefault();
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});

console.log('%c Amulya Gupta Portfolio ', 'background:#1A73E8;color:#fff;padding:6px 12px;border-radius:6px;font-weight:bold;', '\nMLOps & Python AI Engineer | BITS Pilani');
