import edlJson from "./edl.json";

export type Move = {
  /** Scale at shot start / end (1 = fills frame). */
  readonly scaleFrom: number;
  readonly scaleTo: number;
  /** Translation in % of frame at start / end. */
  readonly xFrom: number;
  readonly xTo: number;
  readonly yFrom: number;
  readonly yTo: number;
};

export type Shot = {
  readonly id: string;
  readonly src: string; // relative to public/
  readonly start: number; // seconds on film timeline (fully visible from here)
  readonly end: number; // seconds (fully visible until here)
  readonly fadeIn: number; // dissolve length before `start`
  readonly fadeOut: number; // dissolve length after `end` (only used for fade to black)
  readonly toBlack?: boolean;
  readonly fromBlack?: boolean;
  readonly move: Move;
  readonly focusX: number; // 0..1 horizontal subject position (vertical edition crop)
  readonly focusY: number; // 0..1 vertical subject position (scope matte crop)
  readonly act: string;
};

export type Hemistich = {
  readonly verse: number;
  readonly part: "a" | "b";
  readonly text: string;
  readonly start: number;
  readonly end: number;
};

export type Verse = {
  readonly n: number;
  readonly sadr: Hemistich;
  readonly ajuz: Hemistich;
  readonly showFrom: number;
  readonly showUntil: number;
};

export type Edl = {
  readonly fps: number;
  readonly duration: number;
  readonly audio: string;
  readonly title: { readonly text: string; readonly poet: string; readonly start: number; readonly end: number };
  readonly credits: { readonly lines: readonly string[]; readonly fine?: readonly string[]; readonly start: number; readonly end: number };
  readonly shots: readonly Shot[];
  readonly verses: readonly Verse[];
};

export const edl = edlJson as unknown as Edl;
