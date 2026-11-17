import { Composition } from "remotion";
import { edl } from "./edl";
import { Film } from "./Film";
import { Ember, emberDurationInFrames, emberFps } from "./Ember";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="NisalScope"
        component={Film}
        durationInFrames={Math.round(edl.duration * edl.fps)}
        fps={edl.fps}
        width={1920}
        height={1080}
        defaultProps={{ layout: "scope" as const }}
      />
      <Composition
        id="NisalVertical"
        component={Film}
        durationInFrames={Math.round(edl.duration * edl.fps)}
        fps={edl.fps}
        width={1080}
        height={1920}
        defaultProps={{ layout: "vertical" as const }}
      />
      <Composition
        id="NisalEmber"
        component={Ember}
        durationInFrames={emberDurationInFrames}
        fps={emberFps}
        width={1080}
        height={1920}
      />
    </>
  );
};
