/**
 * «النِصالُ عَلى النِصالِ», the Blades edition: the LETTERS ONLY, on a transparent frame.
 *
 * The picture is cut by pipeline/montage.py and the letters are set into it afterwards by
 * pipeline/comp_text.py (behind foreground subjects, moving with the camera, lit by the shot). So this
 * composition draws nothing but type: each word arrives the moment it is spoken, in its line's place,
 * and the line leaves at its cut. Render it as a PNG sequence with alpha:
 *   npx remotion render BladesText OUT_DIR --sequence --image-format=png --scale=2
 */
import { loadFont } from "@remotion/fonts";
import React from "react";
import { AbsoluteFill, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import bladesJson from "./edl_blades.json";

await Promise.all([
  loadFont({ family: "AmiriB", url: staticFile("fonts/amiri-Amiri-Bold.ttf"), weight: "700" }),
  loadFont({ family: "AmiriB", url: staticFile("fonts/amiri-Amiri-Regular.ttf"), weight: "400" }),
  loadFont({ family: "ArefRuqaaB", url: staticFile("fonts/arefruqaa-ArefRuqaa-Regular.ttf"), weight: "400" }),
  loadFont({ family: "ArefRuqaaB", url: staticFile("fonts/arefruqaa-ArefRuqaa-Bold.ttf"), weight: "700" }),
]);

type Word = { readonly text: string; readonly start: number; readonly em?: boolean };
type Line = {
  readonly id: string;
  readonly words: readonly Word[];
  readonly clear: number; // the line is gone by this time
  readonly out?: number; // seconds of fade before `clear` (0 = leaves on the cut)
  readonly x?: number; // centre, fraction of width
  readonly y: number; // centre, fraction of height
  readonly size: number; // px in the 1080-wide frame
  readonly weight?: 400 | 700;
  readonly family?: "AmiriB" | "ArefRuqaaB";
  readonly color?: string;
  readonly emColor?: string;
  readonly emScale?: number;
  readonly breakAfter?: number; // stack: start a second row after this many words
  readonly lead?: number; // seconds a word appears before its spoken onset
  readonly rise?: number; // seconds of a word's arrival
  readonly allAt?: number; // the whole line arrives together at this time (titles, credits)
  readonly ltr?: boolean;
  readonly tracking?: number;
};
type Edl = { readonly fps: number; readonly duration: number; readonly lines: readonly Line[] };
const edl = bladesJson as unknown as Edl;

export const bladesFps = edl.fps;
export const bladesDurationInFrames = Math.round(edl.duration * edl.fps);

const SOFT = Easing.bezier(0.2, 0.7, 0.2, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const WordSpan: React.FC<{ w: Word; line: Line; t: number }> = ({ w, line, t }) => {
  const rise = line.rise ?? 0.16;
  const a = (line.allAt ?? w.start) - (line.lead ?? 0.06);
  const k = interpolate(t, [a, a + rise], [0, 1], { ...clamp, easing: SOFT });
  const em = w.em === true;
  const scale = em ? interpolate(k, [0, 1], [1.0, line.emScale ?? 1.0]) : 1;
  return (
    <span
      style={{
        display: "inline-block",
        opacity: k,
        filter: k < 1 ? `blur(${((1 - k) * 5).toFixed(2)}px)` : undefined,
        transform: `translateY(${((1 - k) * 0.07 * line.size).toFixed(2)}px) scale(${scale.toFixed(4)})`,
        color: em ? line.emColor ?? line.color ?? "#FFFFFF" : line.color ?? "#FFFFFF",
        marginInline: "0.14em",
        whiteSpace: "nowrap",
      }}
    >
      {w.text}
    </span>
  );
};

const LineBlock: React.FC<{ line: Line }> = ({ line }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  const first = Math.min(...line.words.map((w) => line.allAt ?? w.start)) - (line.lead ?? 0.06);
  if (t < first - 0.02 || t >= line.clear) return null;
  const out = line.out ?? 0;
  const o = out > 0 ? interpolate(t, [line.clear - out, line.clear], [1, 0], clamp) : 1;
  const rows = line.breakAfter ? [line.words.slice(0, line.breakAfter), line.words.slice(line.breakAfter)] : [line.words];
  const lh = line.size * 1.72;
  return (
    <div
      style={{
        position: "absolute",
        left: (line.x ?? 0.5) * width,
        top: line.y * height,
        transform: "translate(-50%, -50%)",
        opacity: o,
        fontFamily: line.family ?? "AmiriB",
        fontWeight: line.weight ?? 700,
        fontSize: line.size,
        lineHeight: `${lh}px`,
        direction: line.ltr ? "ltr" : "rtl",
        letterSpacing: line.tracking ? `${line.tracking}em` : undefined,
        textAlign: "center",
        whiteSpace: "nowrap",
      }}
    >
      {rows.map((r, i) => (
        <div key={i} style={{ height: lh, marginTop: i > 0 ? -line.size * 0.22 : 0 }}>
          {r.map((w, j) => (
            <WordSpan key={`${i}-${j}`} w={w} line={line} t={t} />
          ))}
        </div>
      ))}
    </div>
  );
};

export const BladesText: React.FC = () => (
  <AbsoluteFill>
    {edl.lines.map((l) => (
      <LineBlock key={l.id} line={l} />
    ))}
  </AbsoluteFill>
);
