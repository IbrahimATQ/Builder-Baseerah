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
    readonly y: number; // centre of the two lines, 0..1 of frame height
    readonly gap?: number; // extra px between sadr and ajuz
    readonly size?: number;
    readonly shade?: number; // 0..1 soft shadow pooled behind the words (legibility on bright plates)
    readonly track?: Track; // the camera move the words share (parallax 0..1)
    readonly parallax?: number;
    readonly hide?: readonly ("a" | "b")[]; // a hemistich that is written in the picture itself (burning paper)
    readonly follow?: { readonly k: number; readonly ref: number; readonly from?: number; readonly to?: number }; // words dim with the scene light: (lum/ref)^k
    readonly lit?: { readonly word: number; readonly at: number; readonly glow: number }; // one word lights up (e.g. floodlights on «اللَيالي»)
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

const wordColor = (mode: Mode, lum: number, warm: number): { color: string; glow: string; glowPx: number } => {
  const w = Math.max(0, Math.min(1, warm * 4));
  if (mode === "ember") {
    return { color: interpolateColors(w, [0, 1], ["#FFD9A8", "#FFC27A"]), glow: "rgba(255,110,30,0.55)", glowPx: 26 };
  }
  if (mode === "moon") {
    return { color: "#E6ECF2", glow: "rgba(170,200,235,0.35)", glowPx: 18 };
  }
  if (mode === "ink") {
    return { color: "#24160D", glow: "rgba(0,0,0,0)", glowPx: 0 };
  }
  // light: ivory that takes the scene's warmth; brighter scenes give the words a little bloom
  return {
    color: interpolateColors(w, [0, 1], [IVORY, "#FFE3BF"]),
    glow: `rgba(255,${Math.round(220 - 90 * w)},${Math.round(180 - 120 * w)},${(0.12 + 0.35 * lum).toFixed(3)})`,
    glowPx: 16 + 30 * lum,
  };
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

const SpokenWord: React.FC<{ w: Word; v: JVerse; idx: number; count: number; dimAfter: number | null }> = ({ w, v, idx, count, dimAfter }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const a = w.start - 0.08;
  const on = interpolate(t, [a, a + 0.36], [0, 1], { ...clamp, easing: SOFT });
  const dim = dimAfter === null ? 1 : interpolate(t, [dimAfter, dimAfter + 0.5], [1, 0.82], clamp);
  // the verse leaves word by word, in reading order (right to left), over ~0.9 s
  const k = (t - (v.clear + (idx / Math.max(1, count)) * 0.45)) / 0.55;
  const { lum, warm } = lightAt(t);
  const c = wordColor(v.style.mode, lum, warm);
  const ex = exitStyle(v.style.exit, k, v.style.mode);
  const fo = v.style.follow;
  const followOn = fo && t >= (fo.from ?? -1) && t <= (fo.to ?? 1e9);
  const follow = followOn ? Math.max(0, Math.min(1.08, Math.pow(Math.max(0, lum) / fo.ref, fo.k))) : 1;
  const lw = v.style.lit;
  const litK = lw && lw.word === idx ? interpolate(t, [lw.at, lw.at + 0.5], [0, 1], { ...clamp, easing: SOFT }) : 0;
  const breathe = v.style.mode === "ember" ? 1 + 0.05 * Math.sin(frame * 0.5 + idx) : 1;
  return (
    <span
      style={{
        display: "inline-block",
        marginInline: 10,
        color: c.color,
        textShadow:
          v.style.mode === "ink"
            ? "0 1px 1px rgba(255,240,220,0.18)"
            : litK > 0
              ? `0 0 ${Math.round(10 + 30 * litK * (lw?.glow ?? 1))}px rgba(255,190,110,${(0.25 + 0.5 * litK).toFixed(3)}), 0 0 ${Math.round(c.glowPx * breathe)}px ${c.glow}, 0 2px 10px rgba(0,0,0,0.55)`
              : `0 0 ${Math.round(c.glowPx * breathe)}px ${c.glow}, 0 2px 10px rgba(0,0,0,0.55)`,
        mixBlendMode: v.style.mode === "ink" ? "multiply" : "normal",
        opacity: on * dim * Math.max(follow, litK),
        filter: `blur(${(1 - on) * 6}px)${litK > 0 ? ` brightness(${(1 + 0.25 * litK).toFixed(3)})` : ""}`,
        translate: `0 ${(1 - on) * 14}px`,
        ...ex,
        ...(ex.opacity !== undefined ? { opacity: on * dim * Math.max(follow, litK) * (ex.opacity as number) } : {}),
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
  const hidden = (part: "a" | "b") => (v.style.hide ?? []).includes(part);
  const line = (part: "a" | "b") => (hidden(part) ? [] : v.words.filter((w) => w.part === part && !held(w)));
  const la = line("a"), lb = line("b");
  const all = [...la, ...lb];
  // shared camera move: the words drift with the picture, a little less than it (they float in front)
  let zoom = 1, tx = 0, ty = 0;
  if (s.track) {
    const p = s.parallax ?? 0.6;
    const k = Easing.inOut(Easing.sin)(Math.max(0, Math.min(1, (t - s.track.from) / Math.max(0.01, s.track.to - s.track.from))));
    const z = s.track.z[0] + (s.track.z[1] - s.track.z[0]) * k;
    zoom = 1 + (z / s.track.z[0] - 1) * p;
    tx = -((s.track.dx?.[0] ?? 0) + ((s.track.dx?.[1] ?? 0) - (s.track.dx?.[0] ?? 0)) * k) * 1080 * p;
    ty = -((s.track.dy?.[0] ?? 0) + ((s.track.dy?.[1] ?? 0) - (s.track.dy?.[0] ?? 0)) * k) * 1920 * p;
  }
  const { lum } = lightAt(t);
  const shadeOn = interpolate(t, inc([shown[0].start - 0.4, shown[0].start + 0.2, v.clear + 0.4, v.clear + 1.0]), [0, 1, 1, 0], clamp);
  const shade = (s.shade ?? 0.35) * (0.5 + lum) * shadeOn;
  const lineStyle: React.CSSProperties = {
    fontFamily: "AmiriJ",
    fontSize: s.size ?? 74,
    lineHeight: 1.7,
    direction: "rtl",
    whiteSpace: "nowrap",
    textAlign: "center",
    fontFeatureSettings: '"kern" 1, "liga" 1, "calt" 1',
  };
  const top = s.y * 1920;
  return (
    <AbsoluteFill style={{ scale: String(zoom), translate: `${tx}px ${ty}px` }}>
      {s.mode !== "ink" && shade > 0.01 ? (
        <AbsoluteFill
          style={{
            background: `radial-gradient(ellipse 62% ${9 + (s.gap ?? 0) / 40}% at 50% ${(s.y * 100).toFixed(2)}%, rgba(0,0,0,${Math.min(0.75, shade).toFixed(3)}) 0%, rgba(0,0,0,${Math.min(0.5, shade * 0.6).toFixed(3)}) 45%, rgba(0,0,0,0) 100%)`,
          }}
        />
      ) : null}
      <div style={{ position: "absolute", left: 0, right: 0, top: top - 130 - (s.gap ?? 0) / 2, display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div style={lineStyle}>
          {la.map((w, i) => (
            <SpokenWord key={`a${i}`} w={w} v={v} idx={i} count={all.length} dimAfter={lb.length ? lb[0].start - 0.1 : null} />
          ))}
        </div>
        <div style={{ ...lineStyle, marginTop: s.gap ?? 0 }}>
          {lb.map((w, i) => (
            <SpokenWord key={`b${i}`} w={w} v={v} idx={la.length + i} count={all.length} dimAfter={null} />
          ))}
        </div>
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
        <div key={l} style={{ fontFamily: "AmiriJ", fontSize: 54, color: CHAMPAGNE, direction: "rtl", opacity: 0.94 * o(i * 0.3) }}>
          {l}
        </div>
      ))}
      <div style={{ marginTop: 36, display: "flex", flexDirection: "column", alignItems: "center", gap: 4, opacity: 0.85 * o(0.5), maxWidth: 820 }}>
        {fine.map((f) => (
          <div key={f} style={{ fontFamily: "AmiriJ", fontSize: 29, color: CHAMPAGNE, textAlign: "center", lineHeight: 1.35 }}>
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
