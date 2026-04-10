/** Tailwind helpers for Radix Dialog.Content on narrow viewports + safe area. */
export const DIALOG_CONTENT_SM =
  "w-[calc(100vw-1.5rem)] max-w-[min(400px,calc(100vw-1.5rem))] max-h-[90dvh] overflow-y-auto box-border pb-[max(1rem,env(safe-area-inset-bottom))]";

export const DIALOG_CONTENT_LG =
  "w-[calc(100vw-1.5rem)] max-w-[min(600px,calc(100vw-1.5rem))] max-h-[90dvh] overflow-y-auto box-border pb-[max(1rem,env(safe-area-inset-bottom))]";

/** Wide modal (e.g. war player attack/defense history). */
export const DIALOG_CONTENT_XL =
  "w-[calc(100vw-1.5rem)] max-w-[min(1024px,calc(100vw-1.5rem))] max-h-[90dvh] overflow-y-auto box-border pb-[max(1rem,env(safe-area-inset-bottom))]";

/**
 * Scroll + safe-area only — pair with Dialog.Content `maxWidth` / `width` props.
 * (Radix Themes defaults maxWidth to 600px; Tailwind max-w alone often loses.)
 */
export const DIALOG_CONTENT_SCROLL_SAFE =
  "max-h-[min(90dvh,100dvh-env(safe-area-inset-top)-env(safe-area-inset-bottom))] overflow-y-auto overflow-x-hidden box-border pb-[max(1rem,env(safe-area-inset-bottom))]";

/** Passed to Dialog.Content maxWidth/width — wide on desktop, full-bleed minus gutter on phones. */
export const DIALOG_MAX_W_WIDE = "min(1280px, calc(100vw - 1.5rem))";
