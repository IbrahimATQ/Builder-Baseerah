/**
 * «النِصالُ عَلى النِصالِ», the Blades edition: the LETTERS ONLY, on a transparent frame.
 *
 * The picture is cut by pipeline/montage.py and the letters are set into it afterwards by
 * pipeline/comp_text.py (behind foreground subjects, moving with the camera, lit by the shot). So this
 * composition draws nothing but type: each word arrives the moment it is spoken, in its line's place,
 * and the line leaves at its cut. A line's image-word lands (large, then settling); every block grows a
 * little with its shot's push-in; one word, «تَكَسَّرَتِ», cracks into shards before its cut. Render it as a PNG sequence with alpha:
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

// start = the word's spoken onset; show = when it appears, if that differs (a line's last two words brought on together)
type Word = { readonly text: string; readonly start: number; readonly show?: number; readonly em?: boolean };
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
  readonly push?: number; // the block grows by this fraction over its life, with its shot's push-in (default 0.035)
  readonly breakAt?: number; // the block cracks into shards from this time until it clears (a word that breaks)
};
type Edl = { readonly fps: number; readonly duration: number; readonly lines: readonly Line[] };
const edl = bladesJson as unknown as Edl;

export const bladesFps = edl.fps;
export const bladesDurationInFrames = Math.round(edl.duration * edl.fps);

const SOFT = Easing.bezier(0.2, 0.7, 0.2, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const WordSpan: React.FC<{ w: Word; line: Line; t: number }> = ({ w, line, t }) => {
  const em = w.em === true;
  const rise = line.rise ?? (em ? 0.24 : 0.16);
  const a = (line.allAt ?? w.show ?? w.start) - (line.lead ?? 0.06);
  const k = interpolate(t, [a, a + rise], [0, 1], { ...clamp, easing: SOFT });
  // an ordinary word rises into place; the line's image-word lands: it arrives a little large and settles
  const scale = em ? interpolate(k, [0, 1], [1.16, line.emScale ?? 1.0]) : 1;
  const lift = em ? 0 : (1 - k) * 0.07 * line.size;
  return (
    <span
      style={{
        display: "inline-block",
        opacity: k,
        filter: k < 1 ? `blur(${((1 - k) * (em ? 9 : 5)).toFixed(2)}px)` : undefined,
        transform: `translateY(${lift.toFixed(2)}px) scale(${scale.toFixed(4)})`,
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
  const first = Math.min(...line.words.map((w) => line.allAt ?? w.show ?? w.start)) - (line.lead ?? 0.06);
  if (t < first - 0.02 || t >= line.clear) return null;
  const out = line.out ?? 0;
  const o = out > 0 ? interpolate(t, [line.clear - out, line.clear], [1, 0], clamp) : 1;
  const rows = line.breakAfter ? [line.words.slice(0, line.breakAfter), line.words.slice(line.breakAfter)] : [line.words];
  const lh = line.size * 1.72;
  const grow = 1 + (line.push ?? 0.035) * interpolate(t, [first, line.clear], [0, 1], clamp);
  const body = rows.map((r, i) => (
    <div key={i} style={{ height: lh, marginTop: i > 0 ? -line.size * 0.22 : 0 }}>
      {r.map((w, j) => (
        <WordSpan key={`${i}-${j}`} w={w} line={line} t={t} />
      ))}
    </div>
  ));
  // a word that breaks: the block is cut into slanted shards that part and tilt until the cut takes it
  const p = line.breakAt !== undefined ? interpolate(t, [line.breakAt, line.clear], [0, 1], { ...clamp, easing: Easing.out(Easing.quad) }) : 0;
  const cuts = [-4, 17, 35, 51, 68, 85, 104];
  const shards = cuts.slice(0, -1).map((x0, i) => {
    const x1 = cuts[i + 1];
    const lean = i % 2 === 0 ? 5 : -5;
    return {
      clip: `polygon(${x0 + lean}% -60%, ${x1 + lean}% -60%, ${x1 - lean}% 160%, ${x0 - lean}% 160%)`,
      dx: (i - 2.5) * 0.085 * line.size * p,
      dy: (i % 2 === 0 ? -1 : 1) * 0.07 * line.size * p,
      rot: (i % 2 === 0 ? -1 : 1) * (1.5 + i) * 0.9 * p,
    };
  });
  return (
    <div
      style={{
        position: "absolute",
        left: (line.x ?? 0.5) * width,
        top: line.y * height,
        transform: `translate(-50%, -50%) scale(${grow.toFixed(5)})`,
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
      {p > 0 ? (
        <div style={{ position: "relative" }}>
          {shards.map((sh, i) => (
            <div
              key={i}
              style={{
                position: i === 0 ? "relative" : "absolute",
                inset: 0,
                clipPath: sh.clip,
                transform: `translate(${sh.dx.toFixed(2)}px, ${sh.dy.toFixed(2)}px) rotate(${sh.rot.toFixed(3)}deg)`,
              }}
            >
              {body}
            </div>
          ))}
        </div>
      ) : (
        body
      )}
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
