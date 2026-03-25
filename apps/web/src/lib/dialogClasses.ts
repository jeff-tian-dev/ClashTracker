/** Tailwind helpers for Radix Dialog.Content on narrow viewports + safe area. */
export const DIALOG_CONTENT_SM =
  "w-[calc(100vw-1.5rem)] max-w-[min(400px,calc(100vw-1.5rem))] max-h-[90dvh] overflow-y-auto box-border pb-[max(1rem,env(safe-area-inset-bottom))]";

export const DIALOG_CONTENT_LG =
  "w-[calc(100vw-1.5rem)] max-w-[min(600px,calc(100vw-1.5rem))] max-h-[90dvh] overflow-y-auto box-border pb-[max(1rem,env(safe-area-inset-bottom))]";
