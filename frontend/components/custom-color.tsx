"use client";

import clsx from "clsx";
import { useEffect, useState } from "react";

const HEX = /^#[0-9A-Fa-f]{6}$/;

export function CustomColor({ value, palette, onChange }: { value: string; palette: string[]; onChange: (color: string) => void }) {
  const custom = !palette.includes(value.toUpperCase());
  const [text, setText] = useState(value.toUpperCase());
  useEffect(() => setText(value.toUpperCase()), [value]);
  return (
    <div className="flex items-center gap-2">
      <label
        title="Custom colour"
        className={clsx(
          "relative size-8 cursor-pointer overflow-hidden rounded-lg",
          custom ? "border-[3px] border-text" : "border border-line2",
        )}
        style={{
          background: custom ? value : "conic-gradient(#F0765C, #E0A84E, #A6D86A, #5CC8A8, #6FB7FF, #B69CF0, #E58FB8, #F0765C)",
        }}
      >
        <span className="sr-only">Custom colour</span>
        <input
          type="color"
          aria-label="Custom colour"
          value={HEX.test(value) ? value : "#6FB7FF"}
          onChange={(e) => onChange(e.target.value.toUpperCase())}
          className="absolute inset-0 cursor-pointer opacity-0"
        />
      </label>
      <input
        aria-label="Colour hex code"
        value={text}
        maxLength={7}
        onChange={(e) => {
          const next = e.target.value.startsWith("#") ? e.target.value : `#${e.target.value}`;
          setText(next.toUpperCase());
          if (HEX.test(next)) onChange(next.toUpperCase());
        }}
        className={clsx(
          "h-8 w-[92px] rounded-md border bg-bg px-2 font-mono text-[13px] text-text outline-none",
          HEX.test(text) ? "border-line2 focus:border-accent" : "border-bad",
        )}
      />
    </div>
  );
}
