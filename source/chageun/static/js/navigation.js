// 전체 메뉴는 기본 HTML로도 열립니다. 키보드·화면 전환 시 닫기만 보조합니다.
const mobileMenu = document.querySelector('[data-mobile-menu]');
if (mobileMenu) {
  const summary = mobileMenu.querySelector('summary');
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && mobileMenu.open) {
      mobileMenu.open = false;
      summary.focus();
    }
  });
  document.addEventListener('click', (event) => {
    if (!mobileMenu.contains(event.target)) mobileMenu.open = false;
  });
  const desktop = window.matchMedia('(min-width: 769px)');
  desktop.addEventListener('change', (event) => {
    if (event.matches) mobileMenu.open = false;
  });
}
