const hasGsap = typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined';
    if (hasGsap) gsap.registerPlugin(ScrollTrigger);

    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

    document.addEventListener('DOMContentLoaded', function () {
      const nav = document.getElementById('nav');
      const toggle = document.getElementById('navToggle');
      const links = document.getElementById('navLinks');
      const preloader = document.getElementById('preloader');
      const sub = document.getElementById('heroSub');
      const __subEl = document.getElementById('heroSub');
      const subText = (__subEl && __subEl.dataset.subtext) || "Tangail's biggest technology festival.";
      let lastY = window.scrollY;

      /* preloader */
      if (prefersReduced || !hasGsap) {
        preloader.style.display = 'none';
      } else {
        window.setTimeout(function () {
          preloader.style.pointerEvents = 'none';
        }, 3100);
      }

      /* nav scroll state + hide on scroll down */
      window.addEventListener('scroll', function () {
        const y = window.scrollY;
        nav.classList.toggle('scrolled', y > 40);
        if (!links.classList.contains('open')) {
          nav.classList.toggle('hidden-nav', y > lastY && y > 500);
        }
        lastY = y;
      }, { passive: true });

      /* mobile nav */
      toggle.addEventListener('click', function () {
        const open = links.classList.toggle('open');
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        nav.classList.remove('hidden-nav');
        document.body.style.overflow = open ? 'hidden' : '';
      });
      links.querySelectorAll('a').forEach(function (a) {
        a.addEventListener('click', function () {
          const isGamesToggle = a.parentElement.classList.contains('nav-games');
          if (isGamesToggle) {
            if (window.innerWidth <= 900) {
              a.preventDefault();
              const li = a.parentElement;
              const open = li.classList.toggle('open');
              a.setAttribute('aria-expanded', open ? 'true' : 'false');
              return;
            }
          }
          links.classList.remove('open');
          toggle.setAttribute('aria-expanded', 'false');
          document.body.style.overflow = '';
          nav.classList.remove('hidden-nav');
        });
      });
      window.addEventListener('resize', function () {
        if (window.innerWidth > 900) {
          links.classList.remove('open');
          toggle.setAttribute('aria-expanded', 'false');
          document.body.style.overflow = '';
        }
      });

      /* hero typewriter */
      function typewrite(el, text, speed, done) {
        if (prefersReduced) { el.textContent = text; if (done) done(); return; }
        let i = 0;
        (function step() {
          if (i <= text.length) {
            el.textContent = text.slice(0, i);
            i++;
            window.setTimeout(step, speed);
          } else if (done) { done(); }
        })();
      }

      /* hero entrance choreography */
      if (hasGsap && !prefersReduced) {
        const heroIntro = gsap.timeline({ defaults: { ease: 'power3.out' } });
        heroIntro
          .from('[data-hero-fade]', { opacity: 0, y: 26, duration: 0.8, stagger: 0.12, delay: 2.55 })
          .from('[data-hero-line]', { yPercent: 115, duration: 0.9, stagger: 0.16 }, '-=0.5')
          .from('[data-hero-group] > *', { opacity: 0, y: 30, duration: 0.7, stagger: 0.08 }, '-=0.5');
        heroIntro.eventCallback('onStart', function () { if (sub) typewrite(sub, subText, 14); });
      } else if (sub) {
        sub.textContent = subText;
      }

      /* scroll reveal */
      if (hasGsap && !prefersReduced) {
        gsap.utils.toArray('[data-reveal]').forEach(function (el) {
          gsap.from(el, {
            y: 44, opacity: 0, duration: 0.85, ease: 'power3.out',
            scrollTrigger: { trigger: el, start: 'top 88%', toggleActions: 'play none none reverse' }
          });
        });
      }

      /* counters */
      if (hasGsap && !prefersReduced) {
        gsap.utils.toArray('[data-count]').forEach(function (el) {
          const target = parseInt(el.dataset.count, 10);
          const obj = { val: 0 };
          gsap.to(obj, {
            val: target, duration: 1.6, ease: 'power2.out',
            scrollTrigger: { trigger: el, start: 'top 90%' },
            onUpdate: function () {
              el.textContent = Math.round(obj.val);
            }
          });
        });
      }

      /* timeline line draw */
      if (hasGsap && !prefersReduced) {
        gsap.fromTo('#tlLine',
          { scaleY: 0 },
          {
            scaleY: 1, ease: 'none',
            scrollTrigger: { trigger: '#timeline', start: 'top 60%', end: 'bottom 70%', scrub: 0.5 }
          }
        );
      }

      /* parallax orbs */
      if (hasGsap && !prefersReduced) {
        gsap.utils.toArray('[data-parallax]').forEach(function (el) {
          gsap.to(el, {
            y: parseFloat(el.dataset.parallax), ease: 'none',
            scrollTrigger: { trigger: '.hero', start: 'top top', end: 'bottom top', scrub: 0.8 }
          });
        });
      }

      /* spotlight cards */
      if (hasGsap && finePointer && !prefersReduced) {
        gsap.utils.toArray('.comp-card, .about-stat').forEach(function (card) {
          card.addEventListener('pointermove', function (e) {
            const r = card.getBoundingClientRect();
            card.style.setProperty('--mx', (e.clientX - r.left) + 'px');
            card.style.setProperty('--my', (e.clientY - r.top) + 'px');
          });
        });
      }

      /* magnetic buttons */
      if (hasGsap && finePointer && !prefersReduced) {
        gsap.utils.toArray('[data-magnetic]').forEach(function (el) {
          const strength = 22;
          el.addEventListener('pointermove', function (e) {
            const r = el.getBoundingClientRect();
            const dx = e.clientX - (r.left + r.width / 2);
            const dy = e.clientY - (r.top + r.height / 2);
            gsap.to(el, { x: dx / strength, y: dy / strength, duration: 0.4, ease: 'power3.out' });
          });
          el.addEventListener('pointerleave', function () {
            gsap.to(el, { x: 0, y: 0, duration: 0.6, ease: 'elastic.out(1, 0.35)' });
          });
        });
      }

      /* tilt cards */
      if (hasGsap && finePointer && !prefersReduced) {
        gsap.utils.toArray('[data-tilt]').forEach(function (card) {
          card.addEventListener('pointermove', function (e) {
            const r = card.getBoundingClientRect();
            const rx = ((e.clientY - r.top) / r.height - 0.5) * -8;
            const ry = ((e.clientX - r.left) / r.width - 0.5) * 8;
            gsap.to(card, { rotateX: rx, rotateY: ry, transformPerspective: 700, duration: 0.5, ease: 'power2.out' });
          });
          card.addEventListener('pointerleave', function () {
            gsap.to(card, { rotateX: 0, rotateY: 0, duration: 0.8, ease: 'elastic.out(1, 0.4)' });
          });
        });
      }

      /* scrollspy */
      const spySections = document.querySelectorAll('section[id]');
      const spyLinks = document.querySelectorAll('.nav-link');
      const spy = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          const id = entry.target.id;
          spyLinks.forEach(function (l) {
            l.classList.toggle('active', (l.getAttribute('href') || '').endsWith('#' + id));
          });
        });
      }, { rootMargin: '-40% 0px -55% 0px' });
      spySections.forEach(function (s) { spy.observe(s); });

      /* progress bar + back to top ring */
      const progressBar = document.getElementById('progressBar');
      const toTop = document.getElementById('toTop');
      const ring = toTop.querySelector('.to-top-progress circle');
      const RING_C = 151;
      window.addEventListener('scroll', function () {
        const max = document.documentElement.scrollHeight - window.innerHeight;
        const p = max > 0 ? window.scrollY / max : 0;
        if (!prefersReduced) progressBar.style.transform = 'scaleX(' + p + ')';
        toTop.classList.toggle('show', window.scrollY > 600);
        ring.style.strokeDashoffset = RING_C * (1 - p);
      }, { passive: true });
      toTop.addEventListener('click', function () {
        window.scrollTo({ top: 0, behavior: prefersReduced ? 'auto' : 'smooth' });
      });

      /* cursor glow */
      if (finePointer && !prefersReduced) {
        const glow = document.getElementById('cursorGlow');
        let gx = window.innerWidth / 2, gy = window.innerHeight / 2, cx = gx, cy = gy;
        window.addEventListener('pointermove', function (e) {
          gx = e.clientX; gy = e.clientY;
        }, { passive: true });
        (function raf() {
          cx += (gx - cx) * 0.12;
          cy += (gy - cy) * 0.12;
          glow.style.transform = 'translate(' + (cx - 250) + 'px,' + (cy - 250) + 'px)';
          requestAnimationFrame(raf);
        })();
      }
    });

    /* countdown */
    if (document.getElementById('cDays')) {
      const __cdEl = document.getElementById('countdown');
      const TARGET = new Date((__cdEl && __cdEl.dataset.target) || '2026-09-19T09:00:00+06:00');
      const cDays = document.getElementById('cDays');
      const cHours = document.getElementById('cHours');
      const cMins = document.getElementById('cMins');
      const cSecs = document.getElementById('cSecs');
      let lastSec = '';
      function pad(n) { return String(n).padStart(2, '0'); }
      function updateCountdown() {
        const now = new Date();
        const diff = TARGET - now;
        if (diff <= 0) {
          cDays.textContent = '00'; cHours.textContent = '00';
          cMins.textContent = '00'; cSecs.textContent = '00';
          return;
        }
        const d = Math.floor(diff / 86400000);
        const h = Math.floor((diff % 86400000) / 3600000);
        const m = Math.floor((diff % 3600000) / 60000);
        const s = Math.floor((diff % 60000) / 1000);
        cDays.textContent = pad(d);
        cHours.textContent = pad(h);
        cMins.textContent = pad(m);
        const secStr = pad(s);
        if (secStr !== lastSec && !prefersReduced) {
          cSecs.classList.remove('tick');
          void cSecs.offsetWidth;
          cSecs.classList.add('tick');
        }
        cSecs.textContent = secStr;
        lastSec = secStr;
      }
      updateCountdown();
      setInterval(updateCountdown, 1000);
    }

/* faq */
    function toggleFaq(btn) {
      const item = btn.parentElement;
      const open = item.classList.contains('open');
      document.querySelectorAll('.faq-item.open').forEach(function (el) {
        el.classList.remove('open');
        el.querySelector('.faq-q').setAttribute('aria-expanded', 'false');
      });
      if (!open) {
        item.classList.add('open');
        btn.setAttribute('aria-expanded', 'true');
      }
    }

    
    /* modal removed: registrations use the built-in form (registrations:events) */
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        var navLinksEl = document.getElementById('navLinks');
        if (navLinksEl && navLinksEl.classList.contains('open')) {
          navLinksEl.classList.remove('open');
          document.getElementById('navToggle').setAttribute('aria-expanded', 'false');
          document.body.style.overflow = '';
        }
      }
    });
