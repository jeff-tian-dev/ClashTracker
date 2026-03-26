import { forwardRef } from "react";
import type { ComponentPropsWithoutRef } from "react";

/** Radix Icons has no shield; matches 15×15 filled icon style (e.g. TrashIcon). */
export const ShieldIcon = forwardRef<SVGSVGElement, ComponentPropsWithoutRef<"svg">>((props, ref) => (
  <svg
    width="15"
    height="15"
    viewBox="0 0 15 15"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    ref={ref}
    {...props}
  >
    <path
      fill="currentColor"
      fillRule="evenodd"
      clipRule="evenodd"
      d="M7.5 1L11.75 3.25V7.5C11.75 10.1 9.85 12.35 7.5 13C5.15 12.35 3.25 10.1 3.25 7.5V3.25L7.5 1Z"
    />
  </svg>
));
ShieldIcon.displayName = "ShieldIcon";
