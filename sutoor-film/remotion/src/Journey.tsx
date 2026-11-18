/**
 * «النِصالُ عَلى النِصالِ», the Journey edition: one continuous 4K picture, words that live in it.
 *
 * The picture (real footage, camera moves, grade and transitions) is built beforehand by
 * pipeline/build_picture.py. This composition places the poem inside it:
 *  - each word arrives the moment it is spoken, out of focus and light;
 *  - the words take the scene's light (measured per frame): they dim in the dark, warm by the fire;
 *  - the text block drifts with the camera (parallax), so it sits in the space, not on the glass;
 *  - smoke and embers pass in front of the words;
 *  - each verse leaves in the way of its scene: as ash, on the wind, into smoke, or dissolving.
 */
import { Audio, Video } from "@remotion/media";
import { loadFont } from "@remotion/fonts";
import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  interpolateColors,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import journeyJson from "./edl_journey.json";

await Promise.all([
  loadFont({ family: "AmiriJ", url: staticFile("fonts/amiri-Amiri-Regular.ttf"), weight: "400" }),
  loadFont({ family: "ArefRuqaaJ", url: staticFile("fonts/arefruqaa-ArefRuqaa-Regular.ttf"), weight: "400" }),
]);

type Word = { readonly text: string; readonly start: number; readonly end: number; readonly part: "a" | "b" };
type Exit = "ash" | "wind" | "smoke" | "dissolve" | "burn" | "wash";
type Mode = "light" | "ember" | "ink" | "moon";
type Track = { readonly from: number; readonly to: number; readonly z: readonly [number, number]; readonly dx?: readonly [number, number]; readonly dy?: readonly [number, number] };
type JVerse = {
  readonly n: number;
  readonly words: readonly Word[];
  readonly clear: number; // the verse leaves from here (exit takes ~0.9 s)
  readonly style: {
    readonly mode: Mode;
    readonly exit: Exit;
    readonly y?: number; // (legacy) centre of a two-line block
    readonly gap?: number; // extra px between sadr and ajuz
    readonly size?: number;
    readonly shade?: number; // 0..1 soft shadow pooled behind the words (legibility on bright plates)
    readonly track?: Track; // the camera move the words share (parallax 0..1)
    readonly parallax?: number;
    readonly hide?: readonly ("a" | "b")[]; // a hemistich that is written in the picture itself (burning paper)
    readonly follow?: { readonly k: number; readonly ref: number; readonly from?: number; readonly to?: number }; // words dim with the scene light: (lum/ref)^k
    readonly lit?: { readonly word: number; readonly at: number; readonly glow: number }; // one word lights up (e.g. floodlights on «اللَيالي»)
    readonly ya?: number; // centre of the sadr line (fraction of height)
    readonly yb?: number; // centre of the ajuz line
    readonly levels?: readonly (readonly [number, number])[]; // keyframed level of the letters
    readonly lumRef?: number; // scene light at which the letters sit at their nominal brightness
    readonly recallHidden?: boolean; // a sadr burnt on paper still returns as the recall above the ajuz
    readonly recallUntil?: number; // the recall fades out by this time
  };
};
type Overlay = {
  readonly src: string;
  readonly start: number;
  readonly end: number;
  readonly in?: number; // seconds into the clip
  readonly opacity: number;
  readonly fade?: number;
  readonly blend?: "screen" | "lighten" | "overlay" | "soft-light" | "multiply";
  readonly scale?: number;
  readonly flip?: boolean;
  readonly rate?: number;
  readonly above?: boolean; // in front of the words (default true)
};
type JEdl = {
  readonly fps: number;
  readonly duration: number;
  readonly picture: string;
  readonly audio: string;
  readonly light: { readonly lum: readonly number[]; readonly warm: readonly number[] };
  readonly overlays: readonly Overlay[];
  readonly verses: readonly JVerse[];
  readonly endWord: { readonly text: string; readonly start: number; readonly end: number; readonly y?: number; readonly overlay?: boolean };
  readonly credits: { readonly lines: readonly string[]; readonly fine?: readonly string[]; readonly start: number; readonly end: number };
  readonly title?: { readonly text: string; readonly sub: string; readonly start: number; readonly end: number };
  readonly tints?: readonly (readonly [number, string])[];
};
const edl = journeyJson as unknown as JEdl;

const IVORY = "#F4EBDA";
const CHAMPAGNE = "#D8C49C";
const SOFT = Easing.bezier(0.33, 0, 0.2, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const inc = (pts: number[]): number[] => {
  const out = [...pts];
  for (let i = 1; i < out.length; i++) if (!(out[i] > out[i - 1])) out[i] = out[i - 1] + 0.001;
  return out;
};

/** Scene light at time t, smoothed over ~0.3 s so words breathe with the light rather than flicker. */
const lightAt = (t: number): { lum: number; warm: number } => {
  const { lum, warm } = edl.light;
  const i = Math.round(t * edl.fps);
  let a = 0, b = 0, n = 0;
  for (let k = i - 4; k <= i + 4; k++) {
    if (k >= 0 && k < lum.length) {
      a += lum[k]; b += warm[k]; n++;
    }
  }
  return n ? { lum: a / n, warm: b / n } : { lum: 0.15, warm: 0 };
};

/** Word exit by scene: ash rises and reddens, wind carries it left, smoke lifts it grey, burn chars it. */
const exitStyle = (exit: Exit, k: number, mode: Mode): React.CSSProperties => {
  if (k <= 0) return {};
  const e = SOFT(Math.min(1, k));
  switch (exit) {
    case "ash":
      return { translate: `${4 * e}px ${-38 * e}px`, filter: `blur(${7 * e}px)`, opacity: 1 - e, color: interpolateColors(e, [0, 0.4, 1], ["#FFE6C4", "#FF8A3A", "#4a1a08"]) };
    case "burn":
      return { filter: `blur(${3 * e}px) brightness(${1 + 1.4 * Math.sin(Math.PI * Math.min(1, e * 1.3))})`, opacity: 1 - e * e, color: interpolateColors(e, [0, 0.35, 0.7, 1], [mode === "ink" ? "#24160D" : IVORY, "#FFB060", "#C23A0A", "#120402"]) };
    case "wind":
      return { translate: `${-70 * e}px ${-6 * e}px`, filter: `blur(${9 * e}px)`, opacity: 1 - e, letterSpacing: `${6 * e}px` };
    case "wash":
      return { translate: `${-30 * e}px ${18 * e}px`, filter: `blur(${10 * e}px)`, opacity: 1 - e, color: interpolateColors(e, [0, 1], [IVORY, "#ffffff"]) };
    case "smoke":
      return { translate: `0 ${-24 * e}px`, scale: String(1 + 0.08 * e), filter: `blur(${12 * e}px)`, opacity: 1 - e, color: interpolateColors(e, [0, 1], [IVORY, "#9a9590"]) };
    default:
      return { filter: `blur(${6 * e}px)`, opacity: 1 - e };
  }
};

/** Colour of the words at time t: each shot's own key light (edl.tints), crossfaded over 0.35 s. */
const tintAt = (t: number): string => {
  const tints = edl.tints ?? [];
  if (!tints.length) return IVORY;
  let i = 0;
  while (i + 1 < tints.length && tints[i + 1][0] <= t) i++;
  const [t1, c1] = tints[i];
  const c0 = i > 0 ? tints[i - 1][1] : c1;
  return interpolateColors(Math.min(1, Math.max(0, (t - t1) / 0.35)), [0, 1], [c0, c1]);
};

/** Keyframed level (0..1) of a verse's letters, e.g. dying with the candle. */
const levelAt = (v: JVerse, t: number): number => {
  const ks = v.style.levels;
  if (!ks || !ks.length) return 1;
  if (t <= ks[0][0]) return ks[0][1];
  if (t >= ks[ks.length - 1][0]) return ks[ks.length - 1][1];
  let i = 0;
  while (ks[i + 1][0] <= t) i++;
  const u = (t - ks[i][0]) / Math.max(1e-6, ks[i + 1][0] - ks[i][0]);
  return ks[i][1] + (ks[i + 1][1] - ks[i][1]) * SOFT(u);
};

const SpokenWord: React.FC<{ w: Word; v: JVerse; idx: number; count: number; recallFrom: number | null }> = ({ w, v, idx, count, recallFrom }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  // ink-bleed: alpha up from a 1 px blur to sharp in 0.18 s, no slide, no scale
  const a = w.start - 0.06;
  const on = interpolate(t, [a, a + 0.18], [0, 1], { ...clamp, easing: SOFT });
  // during the ajuz the sadr stays above it as a recall at 45 %
  const recall = recallFrom === null ? 1 : interpolate(t, [recallFrom, recallFrom + 0.4], [1, 0.45], { ...clamp, easing: SOFT });
  // the verse leaves in the pause, in reading order, over ~0.7 s
  const k = (t - (v.clear + (idx / Math.max(1, count)) * 0.25)) / 0.45;
  const { lum } = lightAt(t);
  // the scene's light modulates the letters by about +/-15 %
  const mod = Math.max(0.85, Math.min(1.15, 1 + 0.9 * (lum - (v.style.lumRef ?? 0.18))));
  const ex = exitStyle(v.style.exit, k, v.style.mode);
  const lw = v.style.lit;
  const litK = lw && lw.word === idx ? interpolate(t, [lw.at, lw.at + 0.4], [0, 1], { ...clamp, easing: SOFT }) : 0;
  const col = litK > 0 ? interpolateColors(litK, [0, 1], [tintAt(t), "#FFD9A0"]) : tintAt(t);
  const level = levelAt(v, t);
  const op = on * recall * Math.max(level, litK * 0.9);
  return (
    <span
      style={{
        display: "inline-block",
        marginInline: 11,
        color: col,
        textShadow:
          litK > 0
            ? `0 ${Math.round(6 * litK)}px ${Math.round(18 + 22 * litK)}px rgba(255,170,80,${(0.25 + 0.45 * litK).toFixed(3)}), 0 0 14px rgba(255,220,180,0.25), 0 2px 8px rgba(0,0,0,0.5)`
            : `0 0 16px rgba(255,240,225,${(0.10 + 0.18 * mod - 0.15).toFixed(3)}), 0 2px 8px rgba(0,0,0,0.5)`,
        opacity: op,
        filter: `blur(${(1 - on) * 1.2}px) brightness(${mod.toFixed(3)})`,
        ...ex,
        ...(ex.opacity !== undefined ? { opacity: op * (ex.opacity as number) } : {}),
      }}
    >
      {w.text}
    </span>
  );
};

const VerseBlock: React.FC<{ v: JVerse; isLast: boolean }> = ({ v, isLast }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const shown = v.words.filter((w) => !(v.style.hide ?? []).includes(w.part));
  if (!shown.length || t < shown[0].start - 0.3 || t > v.clear + 1.2) return null;
  const s = v.style;
  const held = (w: Word) => isLast && w.start >= edl.endWord.start - 0.01;
  const hidden = (part: "a" | "b") => (s.hide ?? []).includes(part);
  const sadr = v.words.filter((w) => w.part === "a");
  const ajuz = v.words.filter((w) => w.part === "b");
  // a hidden sadr (it was burning on paper) still returns as the recall above the ajuz
  const la = hidden("a") && !s.recallHidden ? [] : sadr.filter((w) => !held(w));
  const lb = hidden("b") ? [] : ajuz.filter((w) => !held(w));
  const all = [...la, ...lb];
  const recallAt = ajuz.length ? ajuz[0].start - 0.1 : null;
  // a sadr that was on paper appears only as the recall, from the ajuz on
  const sadrFrom = hidden("a") ? (recallAt ?? 0) : 0;
  const lineStyle: React.CSSProperties = {
    position: "absolute",
    left: 0,
    right: 0,
    fontFamily: "AmiriJ",
    fontSize: s.size ?? 86,
    lineHeight: 1.0,
    direction: "rtl",
    whiteSpace: "nowrap",
    textAlign: "center",
    fontFeatureSettings: '"kern" 1, "liga" 1, "calt" 1',
  };
  const ya = (s.ya ?? 0.19) * 1920, yb = (s.yb ?? 0.27) * 1920;
  const fs = s.size ?? 86;
  const sadrOp = hidden("a") ? interpolate(t, [sadrFrom, sadrFrom + 0.4], [0, 1], clamp) : 1;
  const recallEnd = s.recallUntil !== undefined ? interpolate(t, [s.recallUntil - 0.4, s.recallUntil], [1, 0], clamp) : 1;
  return (
    <AbsoluteFill>
      <div style={{ ...lineStyle, top: ya - fs * 0.62, opacity: sadrOp * recallEnd, height: fs * 1.5, paddingTop: fs * 0.12 }}>
        {la.map((w, i) => (
          <SpokenWord key={`a${i}`} w={hidden("a") ? { ...w, start: Math.max(w.start, sadrFrom) } : w} v={v} idx={i} count={all.length} recallFrom={recallAt} />
        ))}
      </div>
      <div style={{ ...lineStyle, top: yb - fs * 0.62, height: fs * 1.5, paddingTop: fs * 0.12 }}>
        {lb.map((w, i) => (
          <SpokenWord key={`b${i}`} w={w} v={v} idx={la.length + i} count={all.length} recallFrom={null} />
        ))}
      </div>
    </AbsoluteFill>
  );
};

/** The poem's last word: it catches fire as it is spoken, burns white-hot, then cools to ash and dark. */
const EndWord: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const { start, end, text } = edl.endWord;
  if (edl.endWord.overlay === false || t < start - 0.2 || t > end + 0.2) return null;
  const k = [start, start + 0.3, start + 1.8, end - 1.0, end - 0.35, end];
  const heat = interpolate(t, inc(k), [0, 1, 1, 0.4, 0.12, 0], { ...clamp, easing: SOFT });
  const core = interpolateColors(heat, [0, 0.25, 0.5, 0.8, 1], ["#2a0602", "#7a1606", "#d2410c", "#ff9a3c", "#fff1cf"]);
  const glow = interpolateColors(heat, [0, 0.5, 1], ["#3a0800", "#c2360a", "#ff7a1a"]);
  const { lum } = lightAt(t);
  const flicker = 1 + 0.05 * Math.sin(frame * 0.9) * Math.sin(frame * 0.37) + 0.25 * (lum - 0.15);
  const r = (x: number) => Math.max(0, Math.round(x * heat * flicker));
  const rise = interpolate(t, [start, end], [0, -26], clamp);
  return (
    <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: (edl.endWord.y ?? 0.45) * 1920 - 200 }}>
      <div
        style={{
          fontFamily: "ArefRuqaaJ",
          fontSize: 220,
          lineHeight: 1.6,
          direction: "rtl",
          color: core,
          opacity: interpolate(t, inc([start, start + 0.14, end - 0.3, end]), [0, 1, 1, 0], clamp),
          textShadow: `0 0 ${r(10)}px ${glow}, 0 0 ${r(34)}px ${glow}, 0 0 ${r(90)}px rgba(255,90,10,${0.55 * heat}), 0 0 ${r(170)}px rgba(255,60,0,${0.35 * heat})`,
          translate: `0 ${rise}px`,
          filter: `blur(${interpolate(t, inc([end - 0.6, end]), [0, 5], clamp)}px)`,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};

const OverlayClip: React.FC<{ o: Overlay }> = ({ o }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps; // local to the Sequence
  const len = o.end - o.start;
  const f = o.fade ?? 0.8;
  const op = o.opacity * interpolate(t, inc([0, f, len - f, len]), [0, 1, 1, 0], { ...clamp, easing: SOFT });
  return (
    <AbsoluteFill style={{ mixBlendMode: o.blend ?? "screen", opacity: op }}>
      <Video
        src={staticFile(o.src)}
        muted
        trimBefore={Math.round((o.in ?? 0) * fps)}
        playbackRate={o.rate ?? 1}
        style={{ width: "100%", height: "100%", objectFit: "cover", scale: `${o.flip ? -(o.scale ?? 1) : o.scale ?? 1} ${o.scale ?? 1}` }}
      />
    </AbsoluteFill>
  );
};

const Credits: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const { start, end, lines } = edl.credits;
  const fine = edl.credits.fine ?? [];
  if (t < start || t > end) return null;
  const o = (d: number) => interpolate(t, inc([start + d, start + d + 0.8, end - 0.7, end]), [0, 1, 1, 0], { ...clamp, easing: SOFT });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column", gap: 16 }}>
      {lines.map((l, i) => (
        <div key={l} style={{ fontFamily: "ArefRuqaaJ", fontSize: 60, color: "#9A4026", direction: "rtl", opacity: 0.95 * o(i * 0.3), textShadow: "0 0 18px rgba(150,40,10,0.35)" }}>
          {l}
        </div>
      ))}
      <div style={{ marginTop: 36, display: "flex", flexDirection: "column", alignItems: "center", gap: 4, opacity: 0.85 * o(0.5), maxWidth: 820 }}>
        {fine.map((f) => (
          <div key={f} style={{ fontFamily: "AmiriJ", fontSize: 25, color: "#7A4A3A", textAlign: "center", lineHeight: 1.35 }}>
            {f}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const Title: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  if (!edl.title || t > edl.title.end) return null;
  const { start, end, text, sub } = edl.title;
  const o = interpolate(t, inc([start, start + 0.7, end - 0.6, end]), [0, 1, 1, 0], { ...clamp, easing: SOFT });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column", gap: 10, opacity: o }}>
      <div style={{ fontFamily: "ArefRuqaaJ", fontSize: 96, color: IVORY, direction: "rtl", textShadow: "0 0 30px rgba(255,170,90,0.35)" }}>{text}</div>
      <div style={{ fontFamily: "AmiriJ", fontSize: 38, color: CHAMPAGNE, direction: "rtl" }}>{sub}</div>
    </AbsoluteFill>
  );
};

export const Journey: React.FC = () => {
  const { fps } = useVideoConfig();
  const seq = (o: Overlay, i: number) => (
    <Sequence key={`${o.src}${i}`} from={Math.round(o.start * fps)} durationInFrames={Math.max(1, Math.round((o.end - o.start) * fps))} layout="none">
      <OverlayClip o={o} />
    </Sequence>
  );
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <AbsoluteFill>
        <Video src={staticFile(edl.picture)} muted style={{ width: "100%", height: "100%" }} />
      </AbsoluteFill>
      {edl.overlays.filter((o) => o.above === false).map(seq)}
      <Title />
      {edl.verses.map((v, i) => (
        <VerseBlock key={v.n} v={v} isLast={i === edl.verses.length - 1} />
      ))}
      <EndWord />
      {edl.overlays.filter((o) => o.above !== false).map(seq)}
      <Credits />
      <Audio src={staticFile(edl.audio)} />
    </AbsoluteFill>
  );
};

export const journeyDurationInFrames = Math.round(edl.duration * edl.fps);
export const journeyFps = edl.fps;
