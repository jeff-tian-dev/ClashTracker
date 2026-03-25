import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  /** When false (e.g. inside a dialog), only scroll — no negative horizontal margin. */
  inset?: boolean;
};

/** Horizontal scroll for wide tables; default negates main horizontal padding on small screens. */
export function TableScrollArea({ children, inset = true }: Props) {
  return (
    <div
      className={
        inset
          ? "w-full overflow-x-auto overscroll-x-contain -mx-4 px-4 md:mx-0 md:px-0"
          : "w-full max-w-full overflow-x-auto overscroll-x-contain"
      }
    >
      {children}
    </div>
  );
}
