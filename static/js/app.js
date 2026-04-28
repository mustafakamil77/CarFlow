'use strict';

/**
 * Sidebar behavior controller.
 * Keeps desktop layout unchanged while enabling mobile off-canvas navigation.
 */
class SidebarController {
  /**
   * @param {{toggleId: string, sidebarId: string, backdropId: string, closeId?: string, desktopMinWidth: number}} options
   */
  constructor(options) {
    this.toggleElement = document.getElementById(options.toggleId);
    this.sidebarElement = document.getElementById(options.sidebarId);
    this.backdropElement = document.getElementById(options.backdropId);
    this.closeElement = document.getElementById(options.closeId || '');
    this.desktopMinWidth = options.desktopMinWidth;

    this.handleToggleClick = this.handleToggleClick.bind(this);
    this.handleBackdropClick = this.handleBackdropClick.bind(this);
    this.handleResize = this.handleResize.bind(this);
    this.handleKeyDown = this.handleKeyDown.bind(this);
    this.handleSidebarClick = this.handleSidebarClick.bind(this);
  }

  init() {
    if (!this.sidebarElement) return;

    if (this.toggleElement) {
      this.toggleElement.addEventListener('click', this.handleToggleClick);
    }
    if (this.closeElement) {
      this.closeElement.addEventListener('click', () => this.close());
    }
    if (this.backdropElement) {
      this.backdropElement.addEventListener('click', this.handleBackdropClick);
    }
    this.sidebarElement.addEventListener('click', this.handleSidebarClick);
    document.addEventListener('keydown', this.handleKeyDown);
    window.addEventListener('resize', this.handleResize, { passive: true });
    this.handleResize();
  }

  setScrollLocked(locked) {
    if (locked) {
      document.documentElement.style.overflow = 'hidden';
      return;
    }
    document.documentElement.style.overflow = '';
  }

  open() {
    this.sidebarElement.classList.remove('-translate-x-full');
    if (this.backdropElement) this.backdropElement.classList.remove('hidden');
    this.setScrollLocked(true);
    if (this.toggleElement) this.toggleElement.setAttribute('aria-expanded', 'true');
  }

  close() {
    this.sidebarElement.classList.add('-translate-x-full');
    if (this.backdropElement) this.backdropElement.classList.add('hidden');
    this.setScrollLocked(false);
    if (this.toggleElement) this.toggleElement.setAttribute('aria-expanded', 'false');
  }

  isOpen() {
    return !this.sidebarElement.classList.contains('-translate-x-full');
  }

  handleToggleClick() {
    if (this.isOpen()) {
      this.close();
      return;
    }
    this.open();
  }

  handleBackdropClick() {
    this.close();
  }

  handleKeyDown(e) {
    if (e.key !== 'Escape') return;
    if (window.innerWidth >= this.desktopMinWidth) return;
    if (!this.isOpen()) return;
    this.close();
  }

  handleSidebarClick(e) {
    const a = e.target && e.target.closest ? e.target.closest('a') : null;
    if (!a) return;
    if (window.innerWidth >= this.desktopMinWidth) return;
    this.close();
  }

  handleResize() {
    const isDesktop = window.innerWidth >= this.desktopMinWidth;
    if (isDesktop) {
      if (this.backdropElement) this.backdropElement.classList.add('hidden');
      this.sidebarElement.classList.remove('-translate-x-full');
      this.setScrollLocked(false);
      if (this.toggleElement) this.toggleElement.setAttribute('aria-expanded', 'false');
      return;
    }
    this.sidebarElement.classList.add('-translate-x-full');
    this.setScrollLocked(false);
    if (this.toggleElement) this.toggleElement.setAttribute('aria-expanded', 'false');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const controller = new SidebarController({
    toggleId: 'sidebarToggle',
    sidebarId: 'sidebar',
    backdropId: 'sidebar-backdrop',
    closeId: 'sidebarClose',
    desktopMinWidth: 768,
  });
  controller.init();
});
