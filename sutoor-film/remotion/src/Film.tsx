import { Audio, Video } from "@remotion/media";
import { loadFont } from "@remotion/fonts";
import React from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { edl, type Hemistich, type Shot, type Verse } from "./edl";

await Promise.all([
  loadFont({ family: "Amiri", url: staticFile("fonts/amiri-Amiri-Regular.ttf"), weight: "400" }),
  loadFont({ family: "Amiri", url: staticFile("fonts/amiri-Amiri-Bold.ttf"), weight: "700" }),
  loadFont({ family: "ArefRuqaa", url: staticFile("fonts/arefruqaa-ArefRuqaa-Regular.ttf"), weight: "400" }),
]);

export type Layout = "scope" | "vertical";
export type FilmProps = { readonly layout: Layout };

/** Warm ivory for verse text, muted champagne for title and credits. */
const IVORY = "#EFE6D2";
const CHAMPAGNE = "#D8C49C";
const SOFT = Easing.bezier(0.33, 0, 0.2, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** Keyframes computed from data can collide when a segment is short; keep them strictly increasing. */
const inc = (pts: number[]): number[] => {
  const out = [...pts];
  for (let i = 1; i < out.length; i++) {
    if (!(out[i] > out[i - 1])) out[i] = out[i - 1] + 0.001;
  }
  return out;
};

/** Picture window for each layout: 2.39:1 scope matte, or 4:5 window in a 9:16 frame. */
const pictureRect = (layout: Layout, width: number, height: number) => {
  if (layout === "scope") {
    const h = Math.round(width / 2.39);
    return { left: 0, top: Math.round((height - h) / 2), width, height: h };
  }
  const h = Math.round((width * 5) / 4);
  return { left: 0, top: 250, width, height: h };
};

const ShotLayer: React.FC<{ shot: Shot; layout: Layout; rect: ReturnType<typeof pictureRect> }> = ({ shot, layout, rect }) => {
  const frame = useCurrentFrame(); // relative to the sequence start (= shot.start - fadeIn)
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const visibleLen = shot.end - shot.start + shot.fadeIn + shot.fadeOut;
  const progress = interpolate(t, [0, visibleLen], [0, 1], clamp);
  const opacity = interpolate(
    t,
    inc([0, Math.max(shot.fadeIn, 0.001), visibleLen - Math.max(shot.fadeOut, 0.001), visibleLen]),
    [shot.fadeIn > 0 ? 0 : 1, 1, 1, shot.toBlack ? 0 : 1],
    { ...clamp, easing: SOFT },
  );
  const m = shot.move;
  // Source is 16:9. Scope: fill width, slide vertically by focusY. Vertical: crop horizontally by focusX.
  const srcAspect = 16 / 9;
  const coverH = rect.width / srcAspect;
  const coverW = rect.height * srcAspect;
  const isScope = layout === "scope";
  const baseW = isScope ? rect.width : Math.max(coverW, rect.width);
  const baseH = isScope ? Math.max(coverH, rect.height) : rect.height;
  const left = isScope ? 0 : -(baseW - rect.width) * shot.focusX;
  const top = isScope ? -(baseH - rect.height) * shot.focusY : 0;
  return (
    <AbsoluteFill style={{ opacity, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          left,
          top,
          width: baseW,
          height: baseH,
          scale: String(interpolate(progress, [0, 1], [m.scaleFrom, m.scaleTo], { ...clamp, easing: Easing.inOut(Easing.sin) })),
          translate: `${interpolate(progress, [0, 1], [m.xFrom, m.xTo], { ...clamp, easing: Easing.inOut(Easing.sin) })}% ${interpolate(progress, [0, 1], [m.yFrom, m.yTo], { ...clamp, easing: Easing.inOut(Easing.sin) })}%`,
        }}
      >
        <Video src={staticFile(shot.src)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
    </AbsoluteFill>
  );
};

const Picture: React.FC<{ layout: Layout }> = ({ layout }) => {
  const { fps, width, height } = useVideoConfig();
  const rect = pictureRect(layout, width, height);
  return (
    <div style={{ position: "absolute", left: rect.left, top: rect.top, width: rect.width, height: rect.height, overflow: "hidden", backgroundColor: "#000" }}>
      {edl.shots.map((shot) => {
        const from = Math.round((shot.start - shot.fadeIn) * fps);
        const dur = Math.round((shot.end - shot.start + shot.fadeIn + shot.fadeOut) * fps);
        return (
          <Sequence key={shot.id} name={shot.id} from={from} durationInFrames={dur} layout="none">
            <ShotLayer shot={shot} layout={layout} rect={rect} />
          </Sequence>
        );
      })}
      {/* Optical vignette: draws the eye inward, darkens corners like a vintage lens. */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse 75% 70% at 50% 48%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.38) 85%, rgba(0,0,0,0.62) 100%)",
          pointerEvents: "none",
        }}
      />
    </div>
  );
};

const lineStyle = (layout: Layout): React.CSSProperties => ({
  fontFamily: "Amiri",
  fontWeight: 400,
  color: IVORY,
  fontSize: layout === "scope" ? 50 : 58,
  lineHeight: 1.75,
  direction: "rtl",
  whiteSpace: "nowrap",
  textShadow: "0 2px 10px rgba(0,0,0,0.55)",
  fontFeatureSettings: '"kern" 1, "liga" 1, "calt" 1',
  letterSpacing: 0,
});

const HemistichText: React.FC<{ h: Hemistich; verse: Verse; layout: Layout }> = ({ h, verse, layout }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const appear = h.start - 0.12;
  const opacity = interpolate(
    t,
    inc([appear, appear + 0.45, verse.showUntil - 0.32, verse.showUntil]),
    [0, 1, 1, 0],
    { ...clamp, easing: SOFT },
  );
  const blur = interpolate(t, [appear, appear + 0.45], [3, 0], clamp);
  const lift = interpolate(t, [appear, appear + 0.6], [6, 0], { ...clamp, easing: SOFT });
  return (
    <span style={{ ...lineStyle(layout), opacity, filter: `blur(${blur}px)`, translate: `0px ${lift}px`, display: "inline-block" }}>
      {h.text}
    </span>
  );
};

/** One bayt. Scope: classical diwan layout, sadr on the right and ajuz on the left of one line,
 *  set in the lower matte so the picture is never covered. Vertical: stacked below the picture. */
const Bayt: React.FC<{ verse: Verse; layout: Layout }> = ({ verse, layout }) => {
  const { width, height } = useVideoConfig();
  const rect = pictureRect(layout, width, height);
  if (layout === "scope") {
    const barTop = rect.top + rect.height;
    return (
      <div
        style={{
          position: "absolute",
          top: barTop,
          left: 0,
          width,
          height: height - barTop,
          display: "flex",
          flexDirection: "row-reverse",
          alignItems: "center",
          justifyContent: "center",
          gap: 110,
        }}
      >
        <div style={{ width: 760, textAlign: "center" }}>
          <HemistichText h={verse.sadr} verse={verse} layout={layout} />
        </div>
        <div style={{ width: 760, textAlign: "center" }}>
          <HemistichText h={verse.ajuz} verse={verse} layout={layout} />
        </div>
      </div>
    );
  }
  const top = rect.top + rect.height + 40;
  return (
    <div style={{ position: "absolute", top, left: 0, width, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <HemistichText h={verse.sadr} verse={verse} layout={layout} />
      <HemistichText h={verse.ajuz} verse={verse} layout={layout} />
    </div>
  );
};

const TitleCard: React.FC<{ layout: Layout }> = ({ layout }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  const { start, end, text, poet } = edl.title;
  const opacity = interpolate(t, inc([start, start + 1.1, end - 0.9, end]), [0, 1, 1, 0], { ...clamp, easing: SOFT });
  const poetOpacity = interpolate(t, inc([start + 0.7, start + 1.7, end - 0.9, end]), [0, 1, 1, 0], { ...clamp, easing: SOFT });
  const rect = pictureRect(layout, width, height);
  const ruleW = interpolate(t, [start + 0.4, start + 1.9], [0, layout === "scope" ? 220 : 200], { ...clamp, easing: SOFT });
  return (
    <div
      style={{
        position: "absolute",
        left: rect.left,
        top: rect.top,
        width: rect.width,
        height: rect.height,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 18,
      }}
    >
      <div
        style={{
          fontFamily: "ArefRuqaa",
          fontSize: layout === "scope" ? 118 : 112,
          color: CHAMPAGNE,
          direction: "rtl",
          opacity,
          textShadow: "0 3px 24px rgba(0,0,0,0.6)",
          lineHeight: 1.5,
        }}
      >
        {text}
      </div>
      <div style={{ width: ruleW, height: 1, backgroundColor: CHAMPAGNE, opacity: 0.55 * poetOpacity }} />
      <div style={{ fontFamily: "Amiri", fontSize: layout === "scope" ? 38 : 42, color: CHAMPAGNE, opacity: 0.85 * poetOpacity, direction: "rtl" }}>
        {poet}
      </div>
    </div>
  );
};

const Credits: React.FC<{ layout: Layout }> = ({ layout }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const { start, end, lines } = edl.credits;
  const fine = edl.credits.fine ?? [];
  const fineOpacity = interpolate(t, inc([start + lines.length * 0.5, start + lines.length * 0.5 + 0.9, end - 0.8, end]), [0, 0.6, 0.6, 0], { ...clamp, easing: SOFT });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 14 }}>
      {lines.map((line, i) => (
        <div
          key={line}
          style={{
            fontFamily: "Amiri",
            fontSize: layout === "scope" ? 36 : 44,
            color: CHAMPAGNE,
            direction: "rtl",
            opacity: interpolate(t, inc([start + i * 0.5, start + i * 0.5 + 0.9, end - 0.8, end]), [0, 0.9, 0.9, 0], { ...clamp, easing: SOFT }),
          }}
        >
          {line}
        </div>
      ))}
      {fine.length > 0 ? (
        <div style={{ marginTop: 26, display: "flex", flexDirection: "column", alignItems: "center", gap: 4, opacity: fineOpacity }}>
          {fine.map((f) => (
            <div key={f} style={{ fontFamily: "Amiri", fontSize: layout === "scope" ? 19 : 24, color: CHAMPAGNE, letterSpacing: 0.3 }}>
              {f}
            </div>
          ))}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

export const Film: React.FC<FilmProps> = ({ layout }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Picture layout={layout} />
      <TitleCard layout={layout} />
      {edl.verses.map((v) => (
        <Bayt key={v.n} verse={v} layout={layout} />
      ))}
      <Credits layout={layout} />
      <Audio src={staticFile(edl.audio)} />
    </AbsoluteFill>
  );
};
