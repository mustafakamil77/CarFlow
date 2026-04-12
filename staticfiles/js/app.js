'use strict';

/**
 * Sidebar behavior controller.
 * Keeps desktop layout unchanged while enabling mobile off-canvas navigation.
 */
class SidebarController {
  /**
   * @param {{toggleId: string, sidebarId: string, backdropId: string, desktopMinWidth: number}} options
   */
  constructor(options) {
    this.toggleElement = document.getElementById(options.toggleId);
    this.sidebarElement = document.getElementById(options.sidebarId);
    this.backdropElement = document.getElementById(options.backdropId);
    this.desktopMinWidth = options.desktopMinWidth;

    this.handleToggleClick = this.handleToggleClick.bind(this);
    this.handleBackdropClick = this.handleBackdropClick.bind(this);
    this.handleResize = this.handleResize.bind(this);
  }

  init() {
    if (!this.sidebarElement) return;

    if (this.toggleElement) {
      this.toggleElement.addEventListener('click', this.handleToggleClick);
    }
    if (this.backdropElement) {
      this.backdropElement.addEventListener('click', this.handleBackdropClick);
    }
    window.addEventListener('resize', this.handleResize, { passive: true });
    this.handleResize();
  }

  open() {
    this.sidebarElement.classList.remove('-translate-x-full');
    if (this.backdropElement) this.backdropElement.classList.remove('hidden');
  }

  close() {
    this.sidebarElement.classList.add('-translate-x-full');
    if (this.backdropElement) this.backdropElement.classList.add('hidden');
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

  handleResize() {
    const isDesktop = window.innerWidth >= this.desktopMinWidth;
    if (isDesktop) {
      if (this.backdropElement) this.backdropElement.classList.add('hidden');
      this.sidebarElement.classList.remove('-translate-x-full');
      return;
    }
    this.sidebarElement.classList.add('-translate-x-full');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const controller = new SidebarController({
    toggleId: 'sidebarToggle',
    sidebarId: 'sidebar',
    backdropId: 'sidebar-backdrop',
    desktopMinWidth: 768,
  });
  controller.init();
});
