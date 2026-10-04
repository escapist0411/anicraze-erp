import './style.css';
import { ERP_URL, SOCIAL_LINKS, STORE_MAP_LINKS } from './config';

document.querySelectorAll<HTMLAnchorElement>('[data-erp-link]').forEach((link) => {
  link.href = ERP_URL;
});

const year = document.querySelector<HTMLElement>('[data-year]');
if (year) year.textContent = String(new Date().getFullYear());

const socialArea = document.querySelector<HTMLElement>('[data-social-links]');
if (socialArea && SOCIAL_LINKS.length) {
  socialArea.replaceChildren(...SOCIAL_LINKS.map(({ label, url }) => {
    const link = document.createElement('a');
    link.textContent = label;
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    return link;
  }));
}

document.querySelectorAll<HTMLElement>('[data-store-code]').forEach((card) => {
  const url = STORE_MAP_LINKS[card.dataset.storeCode ?? ''];
  if (!url) return;
  try {
    if (new URL(url).protocol !== 'https:') return;
    const link = document.createElement('a');
    link.className = 'store-map-link';
    link.href = url;
    link.textContent = 'View map ↗';
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    card.append(link);
  } catch {
    // Ignore an invalid future map configuration.
  }
});

const menuButton = document.querySelector<HTMLButtonElement>('[data-menu-button]');
const menu = document.querySelector<HTMLElement>('[data-mobile-menu]');

function closeMenu() {
  if (!menuButton || !menu) return;
  menuButton.setAttribute('aria-expanded', 'false');
  menuButton.setAttribute('aria-label', 'Open menu');
  menu.hidden = true;
  document.body.classList.remove('menu-open');
}

menuButton?.addEventListener('click', () => {
  if (!menuButton || !menu) return;
  const isOpen = menuButton.getAttribute('aria-expanded') === 'true';
  menuButton.setAttribute('aria-expanded', String(!isOpen));
  menuButton.setAttribute('aria-label', isOpen ? 'Open menu' : 'Close menu');
  menu.hidden = isOpen;
  document.body.classList.toggle('menu-open', !isOpen);
});

menu?.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeMenu));
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') closeMenu();
});
window.matchMedia('(min-width: 861px)').addEventListener('change', (event) => {
  if (event.matches) closeMenu();
});
