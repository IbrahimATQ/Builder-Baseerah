/**
 * «النِصالُ عَلى النِصالِ», the Ember edition: a full-screen 9:16 reel in one world of fire.
 * Each word appears the moment it is spoken; the film closes on a single word that glows like
 * iron from the forge and cools to darkness.
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
import emberJson from "./edl_ember.json";
import type { Edl, Shot, Verse } from "./edl";

await Promise.all([
  loadFont({ family: "AmiriE", url: staticFile("fonts/amiri-Amiri-Regular.ttf"), weight: "400" }),
  loadFont({ family: "ArefRuqaaE", url: staticFile("fonts/arefruqaa-ArefRuqaa-Regular.ttf"), weight: "400" }),
]);

type Word = { readonly text: string; readonly start: number; readonly end: number; readonly part: "a" | "b" };
type EmberVerse = Verse & { readonly words: readonly Word[] };
type EmberEdl = Omit<Edl, "verses"> & {
  readonly verses: readonly EmberVerse[];
  readonly endWord: { readonly text: string; readonly start: number; readonly end: number };
};
const edl = emberJson as unknown as EmberEdl;

const IVORY = "#F2E8D5";
const CHAMPAGNE = "#D8C49C";
const SOFT = Easing.bezier(0.33, 0, 0.2, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const inc = (pts: number[]): number[] => {
  const out = [...pts];
  for (let i = 1; i < out.length; i++) if (!(out[i] > out[i - 1])) out[i] = out[i - 1] + 0.001;
  return out;
};

/** One full-screen shot: dissolve in, slow push, optional fade to black. Shots are pre-cropped to 9:16. */
const EmberShot: React.FC<{ shot: Shot }> = ({ shot }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const len = shot.end - shot.start + shot.fadeIn + shot.fadeOut;
  const opacity = interpolate(
    t,
    inc([0, Math.max(shot.fadeIn, 0.001), len - Math.max(shot.fadeOut, 0.001), len]),
    [shot.fadeIn > 0 ? 0 : 1, 1, 1, shot.toBlack ? 0 : 1],
    { ...clamp, easing: SOFT },
  );
  const scale = interpolate(t, [0, len], [shot.move.scaleFrom, shot.move.scaleTo], { ...clamp, easing: Easing.inOut(Easing.sin) });
  return (
    <AbsoluteFill style={{ opacity, overflow: "hidden" }}>
      <AbsoluteFill style={{ scale: String(scale) }}>
        <Video src={staticFile(shot.src)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/** A word fades up (blur to sharp, slight rise) as it is spoken; it keeps its place in the line from the start. */
const SpokenWord: React.FC<{ w: Word; dimAfter: number | null }> = ({ w, dimAfter }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const a = w.start - 0.06;
  const on = interpolate(t, [a, a + 0.28], [0, 1], { ...clamp, easing: SOFT });
  const dim = dimAfter === null ? 1 : interpolate(t, [dimAfter, dimAfter + 0.4], [1, 0.86], clamp);
  return (
    <span
      style={{
        display: "inline-block",
        opacity: on * dim,
        filter: `blur(${(1 - on) * 4}px)`,
        translate: `0 ${(1 - on) * 10}px`,
        marginInline: 9,
      }}
    >
      {w.text}
    </span>
  );
};

const VerseWords: React.FC<{ v: EmberVerse; isLast: boolean }> = ({ v, isLast }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const until = clearAt(v, isLast);
  const out = interpolate(t, inc([until - 0.3, until]), [1, 0], { ...clamp, easing: SOFT });
  // The poem's last word is not shown in the line: it arrives on its own, glowing, as it is spoken.
  const held = (w: Word) => isLast && w.start >= edl.endWord.start - 0.01;
  const line = (part: "a" | "b") => v.words.filter((w) => w.part === part && !held(w));
  const lineStyle: React.CSSProperties = {
    fontFamily: "AmiriE",
    fontSize: 72,
    lineHeight: 1.75,
    color: IVORY,
    direction: "rtl",
    whiteSpace: "nowrap",
    textAlign: "center",
    textShadow: "0 2px 14px rgba(0,0,0,0.85), 0 0 3px rgba(0,0,0,0.7)",
    fontFeatureSettings: '"kern" 1, "liga" 1, "calt" 1',
  };
  return (
    <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 1110, opacity: out }}>
      <div style={lineStyle}>
        {line("a").map((w, i) => (
          <SpokenWord key={`a${i}`} w={w} dimAfter={v.ajuz.start - 0.1} />
        ))}
      </div>
      <div style={lineStyle}>
        {line("b").map((w, i) => (
          <SpokenWord key={`b${i}`} w={w} dimAfter={null} />
        ))}
      </div>
    </AbsoluteFill>
  );
};

/** The last word, alone on black: white-hot, then cooling through orange and red to darkness. */
const GlowWord: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const { start, end, text } = edl.endWord;
  const k = [start, start + 0.28, start + 1.7, end - 1.0, end - 0.35, end];
  const heat = interpolate(t, inc(k), [0, 1, 1, 0.4, 0.12, 0], { ...clamp, easing: SOFT });
  const core = interpolateColors(heat, [0, 0.25, 0.5, 0.8, 1], ["#2a0602", "#7a1606", "#d2410c", "#ff9a3c", "#fff1cf"]);
  const glow = interpolateColors(heat, [0, 0.5, 1], ["#3a0800", "#c2360a", "#ff7a1a"]);
  const flicker = 1 + 0.035 * Math.sin(frame * 0.9) * Math.sin(frame * 0.37);
  const r = (x: number) => Math.round(x * heat * flicker);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div
        style={{
          fontFamily: "ArefRuqaaE",
          fontSize: 210,
          lineHeight: 1.6,
          direction: "rtl",
          color: core,
          opacity: interpolate(t, inc([start, start + 0.12, end - 0.3, end]), [0, 1, 1, 0], clamp),
          textShadow: `0 0 ${r(10)}px ${glow}, 0 0 ${r(32)}px ${glow}, 0 0 ${r(80)}px rgba(255,90,10,${0.55 * heat}), 0 0 ${r(150)}px rgba(255,60,0,${0.35 * heat})`,
          translate: `0 ${-20}px`,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};

const EndCredits: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const { start, end, lines } = edl.credits;
  const fine = edl.credits.fine ?? [];
  const o = (d: number) => interpolate(t, inc([start + d, start + d + 0.8, end - 0.7, end]), [0, 1, 1, 0], { ...clamp, easing: SOFT });
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column", gap: 16 }}>
      {lines.map((l, i) => (
        <div key={l} style={{ fontFamily: "AmiriE", fontSize: 54, color: CHAMPAGNE, direction: "rtl", opacity: 0.94 * o(i * 0.3) }}>
          {l}
        </div>
      ))}
      <div style={{ marginTop: 36, display: "flex", flexDirection: "column", alignItems: "center", gap: 4, opacity: 0.88 * o(0.5), maxWidth: 780, marginRight: 90 }}>
        {fine.map((f) => (
          <div key={f} style={{ fontFamily: "AmiriE", fontSize: 31, color: CHAMPAGNE, textAlign: "center", lineHeight: 1.35 }}>
            {f}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/** Strength of the dark text band at time t: each shot sets its own (1 = default), blended through dissolves. */
const bandAt = (t: number): number => {
  let b = 1;
  for (const s of edl.shots as readonly (Shot & { band?: number })[]) {
    const v = s.band ?? 1;
    if (t >= s.start - s.fadeIn && t < s.start) b = b + (v - b) * ((t - (s.start - s.fadeIn)) / Math.max(s.fadeIn, 0.001));
    else if (t >= s.start && t <= s.end + 0.05) b = v;
  }
  return b;
};

/** A verse clears at the first picture change after it is fully spoken (never later than showUntil). */
const clearAt = (v: EmberVerse, isLast: boolean): number => {
  if (isLast) return edl.shots[edl.shots.length - 1].end;
  const next = edl.shots.map((s) => s.start - s.fadeIn).filter((c) => c > v.ajuz.end - 0.01).sort((a, b) => a - b)[0];
  return Math.min(v.showUntil, next ?? v.showUntil);
};

const TextBand: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const b = bandAt(frame / fps);
  const a = (x: number) => Math.min(0.85, x * b).toFixed(3);
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse 85% 70% at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.42) 100%), linear-gradient(180deg, rgba(0,0,0,0) 46%, rgba(0,0,0,${a(0.5)}) 58%, rgba(0,0,0,${a(0.55)}) 73%, rgba(0,0,0,${a(0.25)}) 100%)`,
      }}
    />
  );
};

export const Ember: React.FC = () => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {edl.shots.map((shot) => (
        <Sequence
          key={shot.id}
          name={shot.id}
          from={Math.round((shot.start - shot.fadeIn) * fps)}
          durationInFrames={Math.round((shot.end - shot.start + shot.fadeIn + shot.fadeOut) * fps)}
          layout="none"
        >
          <EmberShot shot={shot} />
        </Sequence>
      ))}
      {/* Lens vignette, and a dark band (strength per shot) that keeps the words legible over fire. */}
      <TextBand />
      {edl.verses.map((v, i) => (
        <Sequence key={v.n} name={`verse ${v.n}`} from={0} layout="none">
          <VerseWords v={v} isLast={i === edl.verses.length - 1} />
        </Sequence>
      ))}
      <GlowWord />
      <EndCredits />
      <Audio src={staticFile(edl.audio)} />
    </AbsoluteFill>
  );
};

export const emberDurationInFrames = Math.round(edl.duration * edl.fps);
export const emberFps = edl.fps;
