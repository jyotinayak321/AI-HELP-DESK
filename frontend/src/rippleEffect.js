/**
 * Global button ripple effect. Delegated at the document level so every
 * `.btn` across the app gets it for free — no per-button wiring needed.
 * Pairs with the `.btn::after` / `.btn.rippling::after` / `@keyframes ripple`
 * rules in index.css.
 */
export function initRippleEffect() {
  document.addEventListener('mousedown', (e) => {
    const btn = e.target.closest('.btn');
    if (!btn) return;

    const rect = btn.getBoundingClientRect();
    btn.style.setProperty('--ripple-x', `${e.clientX - rect.left}px`);
    btn.style.setProperty('--ripple-y', `${e.clientY - rect.top}px`);

    btn.classList.remove('rippling');
    // Force reflow so re-triggering the animation on rapid clicks restarts it.
    void btn.offsetWidth;
    btn.classList.add('rippling');
    setTimeout(() => btn.classList.remove('rippling'), 500);
  });
}
